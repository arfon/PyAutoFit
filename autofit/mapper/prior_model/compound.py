from abc import ABC

from autofit.mapper.prior_model.abstract import AbstractPriorModel
from autofit.mapper.prior_model.prior import ArithmeticMixin


class CompoundPrior(AbstractPriorModel, ArithmeticMixin, ABC):
    def __init__(self, left, right):
        super().__init__()
        self.left = left
        self.right = right


class SumPrior(CompoundPrior):
    def instance_for_arguments(self, arguments):
        return self.left.instance_for_arguments(
            arguments
        ) + self.right.instance_for_arguments(
            arguments
        )


class MultiplePrior(CompoundPrior):
    def instance_for_arguments(self, arguments):
        return self.left.instance_for_arguments(
            arguments
        ) * self.right.instance_for_arguments(
            arguments
        )


class NegativePrior(AbstractPriorModel, ArithmeticMixin):
    def __init__(self, prior):
        super().__init__()
        self.prior = prior

    def instance_for_arguments(self, arguments):
        return -self.prior.instance_for_arguments(
            arguments
        )
