# High Level Overview

This is intended to be a high-level documentation of how the code is structured. Whenever possible, [UML](https://en.wikipedia.org/wiki/Unified_Modeling_Language) is used. Some of the standards applied in this documentation can be found [here](https://www.lucidchart.com/pages/uml-class-diagram).

## Workflow

The usual workflow of using the `btyd` library is exemplified in the [User Guide](User Guide.md) page. It can also be represented through the following fluxogram:

![Basic Workflow](https://raw.githubusercontent.com/ColtAllen/btyd/main/docs/source/_static/btyd_workflow.png)

Notice that the right-most branch of the fluxogram actually refers to *monetary value* modeling.

## Models

The core model primitive is the `BaseModel` abstract class inside `__init__.py`, which serves as a *superclass* for all models in BTYD. So far, only the `BetaGeoModel` is set on a higher layer, inheriting from the `BaseModel` and `PredictMixin` abstract classes. `PredictMixin` enforces model prediction conventions for all models except `GammaGammaModel`. The following image shows the UML Class Diagram for all modeling objects:

![models_uml](https://raw.githubusercontent.com/ColtAllen/btyd/main/docs/docs/source/_static/models_uml.png)
If the image is too small, you can go to the source [here](https://raw.githubusercontent.com/ColtAllen/btyd/main/docs/source/_static/models_uml.png).

## Graphs

Graphs are plotted with functions coming from the `plotting.py` file. The main functions are cited below, alongside a brief description of how they are created:

![plotting.py functions](https://raw.githubusercontent.com/ColtAllen/btyd/main/docs/source/_static/btyd_plotting.png)
If the image is too small, you can go to the source [here](https://raw.githubusercontent.com/ColtAllen/btyd/main/docs/source/_static/btyd_plotting.png).

- `plot_period_transactions` : aggregation on how many purchases each customer has made in the calibration period.
- `plot_calibration_purchases_vs_holdout_purchases` : aggregation over the conditional expected number of purchases.
- `plot_frequency_recency_matrix` : conditional expected number of purchases.
- `plot_probability_alive_matrix` : conditional probability of the customer being alive.
- `plot_expected_repeat_purchases` : expected number of purchases.
- `plot_history_alive` : resampling with the model with the specific parameters of the customer, using the `calculate_alive_path` from the `utils.py` file.
- `plot_cumulative_transactions` : plot coming from the `expected_cumulative_transactions` function.
- `plot_incremental_transactions` : decumulative sum over the `expected_cumulative_transactions` function.
- `plot_transaction_rate_heterogeneity` : Gamma Distribution Histogram.
- `plot_dropout_rate_heterogeneity` : Beta Distribution Histogram.

## The `utils.py` File

In the `utils.py` file we can find some useful functions that are used inside the library and listed below:

- `calibration_and_holdout_data` : RFM data separated into calibration and holdout.
- `_find_first_transactions` : DataFrame with the first transactions.
- `summary_data_from_transaction_data` : RFM model for each customer coming from the transactional data.
- `calculate_alive_path` : alive path (history) of a specified customer based on the fitted model.
- `expected_cumulative_transactions` : expected and actual repeated cumulative transactions.