from abc import ABC
from typing import List, Generator, Callable, Type, Union, Tuple

import numpy as np

from autofit import AbstractPriorModel, ModelInstance, Paths, CollectionPriorModel, Result, Analysis, NonLinearSearch
from autofit.non_linear.grid.grid_search import make_lists
from autofit.non_linear.parallel import AbstractJob, Process


class JobResult:
    def __init__(
            self,
            result: Result,
            perturbed_result: Result
    ):
        """
        The result of a single sensitivity comparison

        Parameters
        ----------
        result
        perturbed_result
        """
        self.result = result
        self.perturbed_result = perturbed_result

    @property
    def log_likelihood_difference(self):
        return self.perturbed_result.log_likelihood - self.result.log_likelihood


class Job(AbstractJob):
    def __init__(
            self,
            analysis: Analysis,
            model: AbstractPriorModel,
            perturbation_model: AbstractPriorModel,
            search: NonLinearSearch
    ):
        """
        Job to run non-linear searches comparing how well a model and a model with a perturbation
        fit the image.

        Parameters
        ----------
        model
            A base model that fits the image without a perturbation
        perturbation_model
            A model of the perturbation which has been added to the underlying image
        analysis
            A class definition which can compares instances of a model to a perturbed image
        search
            A non-linear search
        """
        self.analysis = analysis
        self.model = model

        self.perturbation_model = perturbation_model

        paths = search.paths

        self.search = search
        self.perturbed_search = search.copy_with_paths(
            Paths(
                name=paths.name,
                tag=paths.tag + "[perturbed]",
                path_prefix=paths.path_prefix,
                remove_files=paths.remove_files,
            )
        )

    def perform(self) -> JobResult:
        """
        - Create one model with a perturbation and another without
        - Fit each model against the perturbed image

        Returns
        -------
        An object comprising the results of the two fits
        """
        model = CollectionPriorModel()
        model.model = self.model
        result = self.search.fit(
            model=model,
            analysis=self.analysis
        )

        perturbed_model = CollectionPriorModel()
        perturbed_model.perturbation = self.perturbation_model
        perturbed_model.model = self.model

        perturbed_result = self.perturbed_search.fit(
            model=perturbed_model,
            analysis=self.analysis
        )
        return JobResult(
            result=result,
            perturbed_result=perturbed_result
        )


class ImageAnalysis(Analysis, ABC):
    def __init__(self, image: np.array):
        self.image = image


class Sensitivity:
    def __init__(
            self,
            instance,
            model: AbstractPriorModel,
            perturbation_model: AbstractPriorModel,
            image_function: Callable,
            analysis_class: Type[ImageAnalysis],
            search: NonLinearSearch,
            step_size: Union[Tuple[float], float] = 0.1,
            number_of_cores: int = 2
    ):
        """
        Perform sensitivity mapping to evaluate whether a perturbation
        can be detected if it occurs in different parts of an image.

        For a range from 0 to 1 with step_size, for each dimension of the
        perturbation_model, a perturbation is created and used in conjunction
        with the instance to create an image.

        For each of these images, a fit is run with just the model and with both
        the model and perturbation_model to compare how much better the image
        can be fit if the perturbation is included.

        Parameters
        ----------
        instance
            An instance of a model to which perturbations are applied prior to
            images being generated
        model
            A model that fits the instance well
        search
            A NonLinear search class which is copied and used to evaluate fitness
        analysis_class
            A class which can compare an image to an instance and evaluate fitness
        perturbation_model
            A model which provides a perturbations to be applied to the instance
            before creating images
        image_function
            A function that can convert an instance into an image
        step_size
            The size of the step between perturbations. For example, a set size of 0.5
            with a perturbation_model of dimension 3 would give (1 / 0.5) ^ 3 = 8
            distinct perturbations.
        number_of_cores
            How many cores does this computer have? Minimum 2.
        """
        self.instance = instance
        self.model = model

        self.search = search
        self.analysis_class = analysis_class

        self.step_size = step_size
        self.perturbation_model = perturbation_model
        self.image_function = image_function
        self.number_of_cores = number_of_cores

    def run(self) -> List[JobResult]:
        """
        Run fits and comparisons for all perturbations, returning
        a list of results.
        """
        results = list()
        for result in Process.run_jobs(
                self._make_jobs(),
                number_of_cores=self.number_of_cores
        ):
            results.append(result)
        return results

    @property
    def _lists(self) -> List[List[float]]:
        """
        A list of hypercube vectors, used to instantiate
        the perturbation_model and create the individual
        perturbations.
        """
        return make_lists(
            self.perturbation_model.prior_count,
            step_size=self.step_size
        )

    @property
    def _labels(self) -> Generator[str, None, None]:
        """
        One label for each perturbation, used to distinguish
        fits for each perturbation by placing them in separate
        directories.
        """
        for list_ in self._lists:
            strings = list()
            for value, prior_tuple in zip(
                    list_,
                    self.perturbation_model.prior_tuples
            ):
                path, prior = prior_tuple
                value = prior.value_for(
                    value
                )
                strings.append(
                    f"{path}_{value}"
                )
            yield "_".join(strings)

    @property
    def _perturbation_instances(self) -> Generator[
        ModelInstance, None, None
    ]:
        """
        A list of instances each of which defines a perturbation to
        be applied to the image.
        """
        for list_ in self._lists:
            yield self.perturbation_model.instance_from_unit_vector(
                list_
            )

    @property
    def _searches(self) -> Generator[
        NonLinearSearch, None, None
    ]:
        """
        A list of non-linear searches, each of which is applied to
        one perturbation.
        """
        for label in self._labels:
            paths = self.search.paths
            name_path = "{}/{}/{}/{}".format(
                paths.name,
                paths.tag,
                paths.non_linear_tag,
                label,
            )
            yield self._search_instance(
                name_path
            )

    def _search_instance(
            self,
            name_path: str
    ) -> NonLinearSearch:
        """
        Create a search instance, distinguished by its name

        Parameters
        ----------
        name_path
            A path to distinguish this search from other searches

        Returns
        -------
        A non linear search, copied from the instance search
        """
        paths = self.search.paths
        search_instance = self.search.copy_with_paths(
            Paths(
                name=name_path,
                tag=paths.tag,
                path_prefix=paths.path_prefix,
                remove_files=paths.remove_files,
            )
        )

        return search_instance

    def _make_jobs(self) -> Generator[Job, None, None]:
        """
        Create a list of jobs to be run on separate processes.

        Each job fits a perturbed image with the original model
        and a model which includes a perturbation.
        """
        for perturbation_instance, search in zip(
                self._perturbation_instances,
                self._searches
        ):
            instance = ModelInstance()
            instance.model = self.instance
            instance.perturbation = perturbation_instance
            image = self.image_function(
                instance
            )
            yield Job(
                analysis=self.analysis_class(
                    image
                ),
                model=self.model,
                perturbation_model=self.perturbation_model,
                search=search
            )
