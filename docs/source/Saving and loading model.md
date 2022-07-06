### Model Persistence

Model persistence is helpful for saving and loading BTYD models for reuse as well as logging to a registry server such as `mlflow`. After a model has been fit, persistence is handled externally via the [ArViZ](https://python.arviz.org/en/latest/api/inference_data.html) library, which is a transitive dependency of BTYD and installed automatically:

### Fit model

```python
from btyd import BetaGeoModel
from btyd.datasets import load_cdnow_summary

data = load_cdnow_summary(index_col=[0])
bgm = BetaGeoModel()
bgm.fit(data)
bgm
"""<btyd.BetaGeoModel: Parameters {'alpha': 4.5, 'r': 0.2, 'a': 0.8, 'b': 2.4} estimated with 2357 customers.>"""
```

### Saving and Loading Models


```python
import arviz as az

# Save inference data of a fitted model as a JSON:
bgm.idata.to_json('path/to/file.json')

# Load model inference data from a JSON into a new or existing model:
bgm._idata = az.from_json('path/to/file.json')
bgm_new = BetaGeoModel()
bgm_new._idata = az.from_json('path/to/file.json')

bgm_new
"""<btyd.BetaGeoModel: Parameters {'alpha': 4.5, 'r': 0.2, 'a': 0.8, 'b': 2.4} estimated with 2357 customers.>"""
```

The above example persists models in JSON format, but ArViZ supports many other formats and functionalities for model._idata `InferenceData` objects such as plotting as statistical metrics, and is worth taking the time to learn in order to make the most of BTYD.
