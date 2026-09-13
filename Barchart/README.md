# Barchart utilities

The maintained documentation now lives in
docs/barchart-compatibility.md. The runnable demonstrations live under
notebooks/commodities and notebooks/equities.

The Barchart import path contains the deterministic catalog, futures builder,
and normalization helpers:

~~~python
from Barchart import ContinuousFuturesBuilder, agricultural_catalog
~~~

Historical Barchart data is captured by the root package from the official
interactive chart response. No separate anonymous historical endpoint client,
login automation, or browser-download workflow is included.
