# Barchart utilities

The maintained documentation now lives in
docs/barchart-compatibility.md. The runnable demonstrations live under
notebooks/commodities and notebooks/equities.

The Barchart import path contains the deterministic catalog, futures builder,
and normalization helpers:

~~~python
from Barchart import ContinuousFuturesBuilder, agricultural_catalog
~~~

Historical Barchart data is imported through the root package's supported
manual CSV workflow. No automated historical endpoint client is included.
