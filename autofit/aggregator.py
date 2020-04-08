#!/usr/bin/env python

"""
Filter and collate phase dataset in all subdirectories.

Usage:

./aggregator.py (root_directory) [pipeline=pipeline phase=phase dataset=dataset]

Example:

./aggregator.py ../output pipeline=data_mass_x1_source_x1_positions
"""

import os
import pickle
import zipfile
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import List, Union

import autofit.optimize.non_linear.non_linear
from autofit.optimize.non_linear.output import AbstractOutput


class PhaseOutput:
    """
    @DynamicAttrs
    """

    def __init__(self, directory: str):
        """
        Represents the output of a single phase. Comprises a metadata file and other dataset files.

        Parameters
        ----------
        directory
            The directory of the phase
        """
        self.directory = directory
        self.__optimizer = None
        self.__model = None
        self.file_path = os.path.join(directory, "metadata")
        with open(self.file_path) as f:
            self.text = f.read()
            pairs = [
                line.split("=")
                for line
                in self.text.split("\n")
                if "=" in line
            ]
            self.__dict__.update({pair[0]: pair[1] for pair in pairs})

    @property
    def output(self) -> AbstractOutput:
        """
        An object describing the output data from the nonlinear search performed in this phase
        """
        return self.optimizer.output_from_model(
            model=self.model, paths=self.optimizer.paths
        )

    @property
    def model_results(self) -> str:
        """
        Reads the model.results file
        """
        with open(os.path.join(self.directory, "model.results")) as f:
            return f.read()

    @property
    def dataset(self):
        """
        The dataset that this phase ran on
        """
        with open(
                os.path.join(self.directory, f"{self.dataset_name}.pickle"), "rb"
        ) as f:
            return pickle.load(f)

    @property
    def mask(self):
        """
        A pickled mask object
        """
        with open(
                os.path.join(self.directory, "mask.pickle"), "wb"
        ) as f:
            return pickle.load(f)

    @property
    def header(self) -> str:
        """
        A header created by joining the pipeline, phase and dataset names
        """
        return "/".join((self.pipeline, self.phase, self.dataset_name))

    @property
    def optimizer(self) -> autofit.optimize.non_linear.non_linear.NonLinearOptimizer:
        """
        The optimizer object that was used in this phase
        """
        if self.__optimizer is None:
            with open(os.path.join(self.directory, "optimizer.pickle"), "r+b") as f:
                self.__optimizer = pickle.loads(f.read())
        return self.__optimizer

    @property
    def model(self) -> autofit.optimize.non_linear.non_linear.NonLinearOptimizer:
        """
        The optimizer object that was used in this phase
        """
        if self.__model is None:
            with open(os.path.join(self.directory, "model.pickle"), "r+b") as f:
                self.__model = pickle.loads(f.read())
        return self.__model

    def __str__(self):
        return self.text

    def __repr__(self):
        return "<PhaseOutput {}>".format(self)


class AggregatorGroup:
    def __init__(self, groups: ["AbstractAggregator"]):
        """
        A group of aggregators produced by grouping phases on a field.

        Parameters
        ----------
        groups
            Groups, each with a common value in the metadata file
        """
        self.groups = groups

    def filter(self, *args) -> "AggregatorGroup":
        """
        Apply a filter to the underlying groups whilst maintaining the total number of groups.

        Parameters
        ----------
        kwargs
            Key word arguments for filtering

        Returns
        -------
        A collection of groups of the same length with each group having the same or fewer members.
        """
        return AggregatorGroup([group.filter(*args) for group in self.groups])

    def __getitem__(self, item):
        return self.groups[item]

    def __len__(self):
        return len(self.groups)

    def values(self, item):
        return [getattr(group, item) for group in self.groups]


class AttributePredicate:
    def __init__(self, attribute):
        self.attribute = attribute

    def __eq__(self, other):
        return EqualityPredicate(
            self.attribute,
            other
        )

    def __ne__(self, other):
        return ~(self == other)

    def contains(self, value):
        return ContainsPredicate(
            self.attribute,
            value
        )


class AbstractPredicate(ABC):
    def filter(self, phases):
        return filter(
            lambda phase: self(phase),
            phases
        )

    def __invert__(self):
        return NotPredicate(
            self
        )

    @abstractmethod
    def __call__(self, phase):
        pass


class ComparisonPredicate(AbstractPredicate, ABC):
    def __init__(self, attribute, value):
        self.attribute = attribute
        self.value = value


class ContainsPredicate(ComparisonPredicate):
    def __call__(self, phase):
        return self.value in getattr(
            phase,
            self.attribute
        )


class EqualityPredicate(ComparisonPredicate):
    def __call__(self, phase):
        return getattr(
            phase,
            self.attribute
        ) == self.value


class NotPredicate(AbstractPredicate):
    def __init__(self, predicate):
        self.predicate = predicate

    def __call__(self, phase):
        return not self.predicate(
            phase
        )


class AbstractAggregator:
    def __init__(self, phases: List[PhaseOutput]):
        """
        An aggregator that comprises several phases which matching filters.

        Parameters
        ----------
        phases
            Phases that were found to have matching filters
        """
        self.phases = phases

    def __getitem__(
            self,
            item: Union[slice, int]
    ) -> Union[
        "AbstractAggregator",
        PhaseOutput
    ]:
        """
        If an index is passed in then a specific phase output is returned.

        If a slice is passed in then an aggregator comprising several phases is returned.

        Parameters
        ----------
        item
            A slice or index

        Returns
        -------
        An aggregator or phase
        """
        if isinstance(item, slice):
            return AbstractAggregator(
                self.phases[item]
            )
        return self.phases[item]

    def __len__(self):
        return len(self.phases)

    def __getattr__(self, item):
        return AttributePredicate(item)

    def filter(self, *args) -> "AbstractAggregator":
        """
        Filter by key value pairs found in the metadata.

        Another aggregator object is returned.

        Parameters
        ----------
        kwargs
            Key value arguments which are expected to match those found the in metadata file.

        Returns
        -------
        An aggregator comprising all phases that match the filters.
        """
        phases = self.phases
        for predicate in args:
            phases = predicate.filter(phases)
        return AbstractAggregator(phases=list(phases))

    def values(self, item):
        return [getattr(phase, item) for phase in self.phases]

    def map(self, func):
        """
        Map some function onto the aggregated output objects.

        Parameters
        ----------
        func
            A function

        Returns
        -------
        A generator of results
        """
        return map(
            func,
            self.values("output")
        )

    def group_by(self, field: str) -> AggregatorGroup:
        """
        Group the phases by a field, e.g. pipeline.

        The object returned still permits filtering and attribute querying.

        Parameters
        ----------
        field
            The field by which to group

        Returns
        -------
        An object comprising lists of grouped fields
        """
        group_dict = defaultdict(list)
        for phase in self.phases:
            group_dict[getattr(phase, field)].append(phase)
        return AggregatorGroup(list(map(AbstractAggregator, group_dict.values())))

    @property
    def model_results(self) -> str:
        """
        A string joining headers and results for all included phases.
        """
        return "\n\n".join(
            "{}\n\n{}".format(phase.header, phase.model_results)
            for phase in self.phases
        )


class Aggregator(AbstractAggregator):
    def __init__(self, directory: str):
        """
        Class to aggregate phase results for all subdirectories in a given directory.

        The whole directory structure is traversed and a Phase object created for each directory that contains a
        metadata file.

        Parameters
        ----------
        directory
        """
        self._directory = directory
        phases = []

        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                if filename.endswith(".zip"):
                    with zipfile.ZipFile(f"{root}/{filename}", "r") as f:
                        f.extractall(f"{root}/{filename[:-4]}")

        for root, _, filenames in os.walk(directory):
            if "metadata" in filenames:
                phases.append(PhaseOutput(root))

        if len(phases) == 0:
            print(f"\nNo phases found in {directory}\n")
        else:
            paths_string = "\n".join(phase.directory for phase in phases)
            print(f"\nPhases were found in these directories:\n\n{paths_string}\n")
        super().__init__(phases)
