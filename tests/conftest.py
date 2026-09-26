import pandas as pd
import pytest

from med_data.generate import generate_dataset

# The `ui` extra installs pyarrow (a Streamlit dependency). When pyarrow is
# importable, pandas 3 stores strings in Arrow by default. The pipeline gives
# the same results either way, but runs about three times slower with Arrow
# strings, so tests use the Python string storage the pipeline was built with.
pd.set_option("mode.string_storage", "python")


@pytest.fixture(scope="session")
def dataset():
    return generate_dataset()
