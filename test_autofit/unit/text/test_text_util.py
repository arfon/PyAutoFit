import autofit as af
from autofit.text import text_util
import pytest

import os

from autofit.mock import MockClassx2

text_path = "{}/files/samples/".format(os.path.dirname(os.path.realpath(__file__)))


@pytest.fixture(name="model")
def make_model():
    return af.ModelMapper(mock_class=MockClassx2)


@pytest.fixture(name="samples")
def make_samples(model):
    parameters = [[1.0, 2.0], [1.2, 2.2]]

    log_likelihoods = [1.0, 0.0]

    return af.PDFSamples(
        model=model,
        parameters=parameters,
        log_likelihoods=log_likelihoods,
        log_priors=[],
        weights=log_likelihoods,
    )


def test__results_to_file(samples):
    file_results = f"{text_path}model.results"

    text_util.results_to_file(
        samples=samples, filename=file_results, during_analysis=True
    )

    results = open(file_results)

    line = results.readline()

    assert (
        line
        == "Maximum Likelihood                                                                        1.00000000\n"
    )


def test__search_summary_to_file(model):

    file_search_summary = f"{text_path}search.summary"

    parameters = [[1.0, 2.0], [1.2, 2.2]]

    log_likelihoods = [1.0, 0.0]

    samples = af.PDFSamples(
        model=model,
        parameters=parameters,
        log_likelihoods=log_likelihoods,
        log_priors=[],
        weights=log_likelihoods,
        time=None,
    )

    text_util.search_summary_to_file(samples=samples, filename=file_search_summary)

    results = open(file_search_summary)
    lines = results.readlines()
    assert lines[0] == "Total Samples = 2\n"
    results.close()

    samples = af.PDFSamples(
        model=model,
        parameters=parameters,
        log_likelihoods=log_likelihoods + [2.0],
        log_priors=[],
        weights=log_likelihoods,
        time=1,
    )

    text_util.search_summary_to_file(samples=samples, filename=file_search_summary)

    results = open(file_search_summary)
    lines = results.readlines()
    assert lines[0] == "Total Samples = 3\n"
    assert lines[1] == "Time To Run = 1\n"
    results.close()

    samples = af.NestSamples(
        model=model,
        parameters=parameters,
        log_likelihoods=log_likelihoods + [2.0],
        log_priors=[],
        weights=log_likelihoods,
        total_samples=10,
        time=2,
        number_live_points=1,
        log_evidence=1.0,
    )

    text_util.search_summary_to_file(samples=samples, filename=file_search_summary)

    results = open(file_search_summary)
    lines = results.readlines()
    assert lines[0] == "Total Samples = 10\n"
    assert lines[1] == "Total Accepted Samples = 3\n"
    assert lines[2] == "Acceptance Ratio = 0.3\n"
    assert lines[3] == "Time To Run = 2\n"
    results.close()
