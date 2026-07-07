from __future__ import annotations

from jsonschema import Draft202012Validator

from app.errors import ReadinessError, ValidationFailedError
from schemas.strategies import CanonicalStrategy, ExecutionType, ReadinessStatus


class StrategyValidationService:
    def validate_runnable(
        self,
        strategy: CanonicalStrategy,
        *,
        required_execution_type: ExecutionType | None = None,
    ) -> None:
        if not strategy.active or strategy.deprecated:
            raise ReadinessError(
                f"Strategy '{strategy.strategy_id}' is not active.",
                code="strategy_inactive",
            )
        if strategy.readiness != ReadinessStatus.BACKTEST_READY:
            raise ReadinessError(
                f"Strategy '{strategy.strategy_id}' is not backtest ready: {strategy.readiness}.",
                code="strategy_not_backtest_ready",
                details={"readiness": strategy.readiness},
            )
        if required_execution_type and strategy.execution_type != required_execution_type:
            raise ReadinessError(
                (
                    f"Strategy '{strategy.strategy_id}' has execution type "
                    f"{strategy.execution_type}; expected {required_execution_type}."
                ),
                code="unsupported_execution_type",
                details={
                    "strategy_execution_type": strategy.execution_type,
                    "required_execution_type": required_execution_type,
                },
            )

    def validate_parameters(self, strategy: CanonicalStrategy, parameters: dict) -> dict:
        merged = dict(strategy.default_parameters)
        merged.update(parameters or {})
        schema = strategy.parameter_schema or {"type": "object", "properties": {}}
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(merged), key=lambda error: list(error.path))
        if errors:
            messages = [".".join(str(part) for part in error.path) + f": {error.message}" for error in errors]
            raise ValidationFailedError(
                f"Invalid parameters for strategy '{strategy.strategy_id}'.",
                code="invalid_strategy_parameters",
                details={"errors": messages},
            )
        return merged
