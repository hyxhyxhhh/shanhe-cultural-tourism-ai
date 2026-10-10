"""Server-side prerequisite rules for steps five through nine."""

from collections.abc import Mapping


REQUIRED_CONFIRMED_STEPS: dict[int, tuple[int, ...]] = {
    5: (4,),
    6: (5,),
    7: (5, 6),
    8: (7,),
    9: (8,),
}


def assert_can_generate(step_no: int, statuses: Mapping[int, str]) -> None:
    required = REQUIRED_CONFIRMED_STEPS.get(step_no)
    if required is None:
        raise ValueError("only steps 5 through 9 are owned by this service")
    missing = [number for number in required if statuses.get(number) != "confirmed"]
    if missing:
        raise ValueError(f"steps not confirmed: {','.join(str(number) for number in missing)}")
