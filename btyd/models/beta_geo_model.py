from __future__ import generator_stop
from __future__ import annotations
import warnings

from typing import Union, Tuple, Dict

import pandas as pd
import numpy as np
import numpy.typing as npt

import pymc as pm
import aesara.tensor as at

from scipy.special import gammaln, beta, gamma
from scipy.special import hyp2f1
from scipy.special import expit

from . import BaseModel, PredictMixin
from ..utils import _scale_time, _check_inputs
from ..generate_data import beta_geometric_nbd_model


class BetaGeoModel(PredictMixin['BetaGeoModel'], BaseModel['BetaGeoModel']):
    """
    Also known as the BG/NBD model.
    Based on [2]_, this model has the following assumptions:
    1) Each individual, i, has a hidden lambda_i and p_i parameter
    2) These come from a population wide Gamma and a Beta distribution
       respectively.
    3) Individuals purchases follow a Poisson process with rate lambda_i*t .
    4) After each purchase, an individual has a p_i probability of dieing
       (never buying again).
    
    Parameters
    ----------
    hyperparams: dict
        Dictionary containing hyperparameters for model prior parameter distributions.

    Attributes
    ----------
    params_: :obj: Series
        The fitted parameters of the model
    data: :obj: DataFrame
        A DataFrame with the values given in the call to `fit`
    attr_name : datatype
        Add description here.
        
    References
    ----------
    .. [2] Fader, Peter S., Bruce G.S. Hardie, and Ka Lok Lee (2005a),
       "Counting Your Customers the Easy Way: An Alternative to the
       Pareto/NBD Model," Marketing Science, 24 (2), 275-84.

    """

    def __init__(self, hyperparams: Dict[float] = None) -> SELF:

        if hyperparams is None:
            self._hyperparams = {
                'alpha_prior_alpha': 1.,
                'alpha_prior_beta': 6.,
                'r_prior_alpha': 1.,
                'r_prior_beta': 1.,
                'phi_prior_lower': 0.,
                'phi_prior_upper': 1.,
                'kappa_prior_alpha': 1.,
                'kappa_prior_m': 1.5,
            }
        else:
            self._hyperparams = hyperparams
    
    _param_list = ['alpha','r', 'a', 'b']

    def _model(self) -> pm.Model():

        with pm.Model(name=f'{self.__class__.__name__}') as self.model:
            # Priors for lambda parameters.
            alpha_prior = pm.Weibull(
                name="alpha", 
                alpha=self._hyperparams.get('alpha_prior_alpha'), 
                beta=self._hyperparams.get('alpha_prior_beta'),
                )
            r_prior = pm.Weibull(
                name="r", 
                alpha=self._hyperparams.get('r_prior_alpha'), 
                beta=self._hyperparams.get('r_prior_beta'),
                )

            # Heirarchical pooling of hyperparams for beta parameters.
            phi_prior = pm.Uniform(
                'phi', 
                lower=self._hyperparams.get('phi_prior_lower'), 
                upper=self._hyperparams.get('phi_prior_upper'),
                )
            kappa_prior = pm.Pareto(
                'kappa',
                alpha=self._hyperparams.get('kappa_prior_alpha'),
                m=self._hyperparams.get('kappa_prior_m'),
                )

            # Beta parameters.
            a = pm.Deterministic("a", phi_prior*kappa_prior)
            b = pm.Deterministic("b", (1.0-phi_prior)*kappa_prior)

            logp = pm.Potential('loglike', self._log_likelihood(self._frequency, self._recency, self._T, a, b, alpha_prior, r_prior))
        
        return self.model

    def _log_likelihood(
        self, 
        frequency: npt.ArrayLike, 
        recency: npt.ArrayLike, 
        T: at.var.TensorVariable, 
        a: at.var.TensorVariable, 
        b: at.var.TensorVariable, 
        alpha: at.var.TensorVariable, 
        r: at.var.TensorVariable,
        testing: bool = False
        ) -> Union[Tuple[at.var.TensorVariable],at.var.TensorVariable]:
        """Log-likelihood function to estimate model parameters for entire population of customers.

        This function was originally introduced in equation 6 of [2]_, and reformulated in section 7 of [3]_
        to avoid numerical errors for customers who have made large numbers of transactions. 
        More information can be found in [4]_.

        Parameters
        ----------
        frequency: int
            Total number of transactions for each customer.
        recency: float64
            Path where to save model.
        T: float64
            Total date periods for each customer.
        a: aesara TensorVariable
            Tensor for 'a' parameter of Beta distribution.
        b: aesara TensorVariable
            Tensor for 'b' parameter of Beta distribution.
        alpha: aesara TensorVariable
            Tensor for 'beta' parameter of Gamma distribution.
        r: aesara TensorVariable
            Tensor for 'alpha' parameter of Gamma distribution. 
        testing: bool
            Testing flag for term validation. Do not use in production.

        Returns
        ----------
        loglike: aesara TensorVariable
            Log-likelihood value for self._model().

        References
        ----------
        .. [2] Fader, Peter S., Bruce G.S. Hardie, and Ka Lok Lee (2005a),
        "Counting Your Customers the Easy Way: An Alternative to the
        Pareto/NBD Model," Marketing Science, 24 (2), 275-84.
        .. [3] http://brucehardie.com/notes/027/bgnbd_num_error.pdf
        .. [4] http://brucehardie.com/notes/004/
        """

        # Recast inputs as Aesara tensor variables
        x = at.as_tensor_variable(frequency)
        t_x = at.as_tensor_variable(recency)
        T = at.as_tensor_variable(T)

        x_zero = at.where(x>0, 1, 0)

        # Refactored for numerical error
        d1 = at.gammaln(r + x) - at.gammaln(r) + at.gammaln(a + b) + at.gammaln(b + x) - at.gammaln(b) - at.gammaln(a + b + x)
        d2 = r * at.log(alpha) - (r + x) * at.log(alpha + t_x)
        c3 = ((alpha + t_x)/(alpha + T))**(r+x)
        c4 = a/(b+x-1)

        if testing:
            return d1.eval(),d2.eval(),c3.eval(),c4.eval()
        
        else:
            ll_2 = at.log(at.switch(x_zero, at.sum(c3+c4),c3))

            loglike = d1 + d2 + at.log(c3 + c4 * at.switch(x_zero, 1, 0))
            
            return loglike

    def _conditional_expected_number_of_purchases_up_to_time(
        self, 
        t: npt.ArrayLike = None,
        n: int = None,
        posterior: bool = False,
        posterior_draws: int = 100,
        frequency:npt.ArrayLike = None,
        recency:npt.ArrayLike = None,
        T:npt.ArrayLike = None
        ) -> Union[float,np.ndarray]:
        """
        Conditional expected number of purchases up to time.

        Calculate the expected number of repeat purchases up to time t for a
        randomly chosen individual from the population, given they have
        purchase history (frequency, recency, T).

        This function uses equation (10) from [2]_.

        Parameters
        ----------
        t: array_like
            times to calculate the expectation for.
        frequency: array_like
            historical frequency of customer.
        recency: array_like
            historical recency of customer.
        T: array_like
            age of the customer.

        Returns
        -------
        float

        References
        ----------
        .. [2] Fader, Peter S., Bruce G.S. Hardie, and Ka Lok Lee (2005a),
        "Counting Your Customers the Easy Way: An Alternative to the
        Pareto/NBD Model," Marketing Science, 24 (2), 275-84.
        """

        # To get rid of these arguments and IF statements, the pertinent unit test must be refactored.
        if frequency is None:
            x = self._frequency
        else:
            x = frequency
        if recency is None:
            recency = self._recency
        if T is None:
            T = self._T
        
        self._alpha, self._r, self._a, self._b = self._unload_params(posterior,posterior_draws)

        alpha = self._alpha
        r = self._r
        a = self._a
        b = self._b
        
        _a = r + x
        _b = b + x
        _c = a + b + x - 1
        _z = t / (alpha + T + t)
        ln_hyp_term = np.log(hyp2f1(_a, _b, _c, _z))

        # if the value is inf, we are using a different but equivalent
        # formula to compute the function evaluation.
        ln_hyp_term_alt = np.log(hyp2f1(_c - _a, _c - _b, _c, _z)) + (_c - _a - _b) * np.log(1 - _z)
        ln_hyp_term = np.where(np.isinf(ln_hyp_term), ln_hyp_term_alt, ln_hyp_term)
        first_term = (a + b + x - 1) / (a - 1)
        second_term = 1 - np.exp(ln_hyp_term + (r + x) * np.log((alpha + T) / (alpha + t + T)))

        numerator = first_term * second_term
        denominator = 1 + (x > 0) * (a / (b + x - 1)) * ((alpha + T) / (alpha + recency)) ** (r + x)

        return numerator / denominator

    def _conditional_probability_alive(
        self,
        t: npt.ArrayLike = None,
        n: int = None,
        posterior: bool = False,
        posterior_draws: int = 100,
        frequency:npt.ArrayLike = None,
        recency:npt.ArrayLike = None,
        T:npt.ArrayLike = None
        ) -> np.ndarray:
        """
        Compute conditional probability alive.

        Compute the probability that a customer with history
        (frequency, recency, T) is currently alive.

        From http://www.brucehardie.com/notes/021/palive_for_BGNBD.pdf

        Parameters
        ----------
        frequency: array or scalar
            historical frequency of customer.
        recency: array or scalar
            historical recency of customer.
        T: array or scalar
            age of the customer.

        Returns
        -------
        array
            value representing a probability
        """

        # To get rid of these arguments and IF statements, the pertinent unit test must be refactored.
        if frequency is None:
            frequency = self._frequency
        if recency is None:
            recency = self._recency
        if T is None:
            T = self._T

        self._alpha, self._r, self._a, self._b = self._unload_params(posterior,posterior_draws)

        alpha = self._alpha
        r = self._r
        a = self._a
        b = self._b

        log_div = (r + frequency) * np.log((alpha + T) / (alpha + recency)) + np.log(
            a / (b + np.maximum(frequency, 1) - 1)
        )

        return np.atleast_1d(np.where(frequency == 0, 1.0, expit(-log_div)))

    def _expected_number_of_purchases_up_to_time(
        self, 
        t: npt.ArrayLike = None,
        n: int = None,
        posterior: bool = False,
        posterior_draws: int = 100,
        ) -> Union[float,np.ndarray]:
        """
        Calculate the expected number of repeat purchases up to time t.

        Calculate repeat purchases for a randomly chosen individual from the
        population.

        Equivalent to equation (9) of [2]_.

        Parameters
        ----------
        t: array_like
            times to calculate the expection for

        Returns
        -------
        float

        References
        ----------
        .. [2] Fader, Peter S., Bruce G.S. Hardie, and Ka Lok Lee (2005a),
        "Counting Your Customers the Easy Way: An Alternative to the
        Pareto/NBD Model," Marketing Science, 24 (2), 275-84.
        """

        self._alpha, self._r, self._a, self._b = self._unload_params(posterior,posterior_draws)

        alpha = self._alpha
        r = self._r
        a = self._a
        b = self._b

        hyp = hyp2f1(r, b, a + b - 1, t / (alpha + t))

        return (a + b - 1) / (a - 1) * (1 - hyp * (alpha / (alpha + t)) ** r)

    def _probability_of_n_purchases_up_to_time(
        self, 
        t: float = None, 
        n: int = None,
        posterior: bool = False,
        posterior_draws: int = 100,
        ) -> Union[np.ndarray,float]:
        """
        Compute the probability of n purchases.

         .. math::  P( N(t) = n | \text{model} )

        where N(t) is the number of repeat purchases a customer makes in t
        units of time.

        Comes from equation (8) of [2]_.

        Parameters
        ----------
        t: float
            number units of time
        n: int
            number of purchases

        Returns
        -------
        float:
            Probability to have n purchases up to t units of time

        References
        ----------
        .. [2] Fader, Peter S., Bruce G.S. Hardie, and Ka Lok Lee (2005a),
        "Counting Your Customers the Easy Way: An Alternative to the
        Pareto/NBD Model," Marketing Science, 24 (2), 275-84.
        """

        # _alpha, _r, _a, _b = self._unload_params(posterior,posterior_draws)
        # Repeat param arrays for len n.
        # alpha, r, a, b = [np.tile(_param,(1,n)) for _param in [alpha, r, a, b]]

        param_arrays = self._unload_params(posterior,posterior_draws)
        
        if not posterior:
            param_arrays = [np.array(_param).reshape(1,) for _param in param_arrays]

        prob_n_purchases = []

        for alpha, r, a, b in zip(param_arrays[0], param_arrays[1], param_arrays[2], param_arrays[3]):

            first_term = (
                beta(a, b + n)
                / beta(a, b)
                * gamma(r + n)
                / gamma(r)
                / gamma(n + 1)
                * (alpha / (alpha + t)) ** r
                * (t / (alpha + t)) ** n
            )

            if n > 0:
                # create array of len(n) and transpose.
                # n_range = np.arange(0, n).T 
                j = np.arange(0, n)
                # repeat n_range array for len of posterior draws.
                # j = np.tile(n_range,(posterior_draws,1))  
                finite_sum = (gamma(r + j) / gamma(r) / gamma(j + 1) * (t / (alpha + t)) ** j).sum()
                second_term = beta(a + 1, b + n - 1) / beta(a, b) * (1 - (alpha / (alpha + t)) ** r * finite_sum)
            else:
                second_term = 0
        
            prob_n_purchase = first_term + second_term

            prob_n_purchases.append(prob_n_purchase)

        return np.array(prob_n_purchases)
    
    # BETA TODO: this attribute can be removed after the attribute resolution order issue of PredictMixin is resolved.
    _quantities_of_interest = {
        'cond_prob_alive': _conditional_probability_alive,
        'cond_n_prchs_to_time': _conditional_expected_number_of_purchases_up_to_time,
        'n_prchs_to_time': _expected_number_of_purchases_up_to_time,
        'prob_n_prchs_to_time': _probability_of_n_purchases_up_to_time,
        }
    
    def generate_rfm_data(self, size:int = 1000) -> pd.DataFrame:
        """
        Generate synthetic RFM data from fitted model parameters. Useful for posterior predictive checks of model performance.

        Parameters
        ----------
        t: int
            rows of synthetic RFM data to generate. Default is 1000.

        Returns
        -------
        pd.DataFrame
            dataframe containing ["frequency", "recency", "T", "lambda", "p", "alive", "customer_id"] columns.

        """
        
        alpha, r, a, b = self._unload_params()

        self.synthetic_df = beta_geometric_nbd_model(
            self._T, r, alpha, a, b, size=size
            )
        
        return self.synthetic_df
    