from io import BytesIO

from plot_studio.services.csv_reading import (
    detect_separator_from_sample,
    read_csv_input,
)


class UploadedBytes(BytesIO):
    def __init__(self, name: str, content: str):
        super().__init__(content.encode("utf-8"))
        self.name = name


def test_detect_separator_from_tab_sample():
    sample = "a\tb\tc\n1\t2\t3\n4\t5\t6\n"
    assert detect_separator_from_sample(sample) == "\t"


def test_read_csv_input_from_uploaded_file_trims_object_columns():
    uploaded = UploadedBytes("sample.csv", "name,value\n  alpha  ,1\nbeta,2\n")

    df, label, err = read_csv_input(
        uploaded,
        "",
        decimal=".",
        sep=",",
        header=0,
        skiprows=None,
    )

    assert err is None
    assert label == "sample.csv"
    assert df is not None
    assert df["name"].tolist() == ["alpha", "beta"]
