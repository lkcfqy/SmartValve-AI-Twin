"""Outcome-blind Paderborn identity/operating-setting split manifest.

This module contains metadata-only split declarations.  Importing it never opens a
Paderborn archive, which keeps the D2 outcome seal intact while the development
protocol is being finalized on D0/D1.
"""

from __future__ import annotations

from dataclasses import dataclass

from smartvalve.data.paderborn import (
    BEARING_METADATA,
    COMPOUND_BEARING_CODES,
    OPERATING_SETTINGS,
    PRIMARY_BEARING_CODES,
)


@dataclass(frozen=True)
class PaderbornIdentityFold:
    """One predeclared group of held-out pure-class bearing identities."""

    fold_id: str
    bearing_codes: tuple[str, ...]


@dataclass(frozen=True)
class PaderbornOuterFold:
    """One crossed asset/setting split for strict double-unseen evaluation."""

    fold_id: str
    identity_fold_id: str
    held_bearing_codes: tuple[str, ...]
    held_setting_code: str


# This assignment uses only the official bearing metadata.  Five folds contain
# one artificial and one real asset for each damaged pure class.  The sixth must
# contain two artificial outer assets and one real inner asset because the corpus
# has 7/5 artificial/real outer assets and 5/6 artificial/real inner assets.
PADERBORN_IDENTITY_FOLDS = (
    PaderbornIdentityFold(
        "identity=0", ("K001", "KA01", "KA04", "KI01", "KI04")
    ),
    PaderbornIdentityFold(
        "identity=1", ("K002", "KA03", "KA15", "KI03", "KI14")
    ),
    PaderbornIdentityFold(
        "identity=2", ("K003", "KA05", "KA16", "KI05", "KI16")
    ),
    PaderbornIdentityFold(
        "identity=3", ("K004", "KA06", "KA22", "KI07", "KI17")
    ),
    PaderbornIdentityFold(
        "identity=4", ("K005", "KA07", "KA30", "KI08", "KI18")
    ),
    PaderbornIdentityFold("identity=5", ("K006", "KA08", "KA09", "KI21")),
)


def build_paderborn_outer_folds() -> tuple[PaderbornOuterFold, ...]:
    """Cross six identity folds with four official operating settings."""

    validate_paderborn_identity_folds(PADERBORN_IDENTITY_FOLDS)
    return tuple(
        PaderbornOuterFold(
            fold_id=f"{identity_fold.fold_id}|setting={setting.code}",
            identity_fold_id=identity_fold.fold_id,
            held_bearing_codes=identity_fold.bearing_codes,
            held_setting_code=setting.code,
        )
        for identity_fold in PADERBORN_IDENTITY_FOLDS
        for setting in OPERATING_SETTINGS
    )


def validate_paderborn_identity_folds(
    folds: tuple[PaderbornIdentityFold, ...],
) -> None:
    """Reject leakage, omissions, class imbalance, or compound-label collapse."""

    if len(folds) != 6 or len({fold.fold_id for fold in folds}) != 6:
        raise ValueError("Paderborn requires six uniquely named identity folds")

    metadata = {bearing.code: bearing for bearing in BEARING_METADATA}
    flattened = tuple(code for fold in folds for code in fold.bearing_codes)
    if len(flattened) != len(set(flattened)):
        raise ValueError("a Paderborn bearing identity appears in more than one fold")
    if set(flattened) != set(PRIMARY_BEARING_CODES):
        missing = sorted(set(PRIMARY_BEARING_CODES) - set(flattened))
        unexpected = sorted(set(flattened) - set(PRIMARY_BEARING_CODES))
        raise ValueError(
            "identity folds must cover each pure-class bearing exactly once: "
            f"missing={missing}, unexpected={unexpected}"
        )
    if set(flattened) & set(COMPOUND_BEARING_CODES):
        raise ValueError("compound bearings cannot enter the closed-set identity folds")

    expected_inner_counts = [1, 2, 2, 2, 2, 2]
    observed_inner_counts: list[int] = []
    for fold in folds:
        items = [metadata[code] for code in fold.bearing_codes]
        label_counts = {
            label: sum(item.primary_label == label for item in items)
            for label in ("healthy", "outer", "inner")
        }
        if label_counts["healthy"] != 1 or label_counts["outer"] != 2:
            raise ValueError(
                f"{fold.fold_id} must hold one healthy and two outer bearings"
            )
        observed_inner_counts.append(label_counts["inner"])

        damage_origins = {
            item.damage_origin
            for item in items
            if item.primary_label in {"outer", "inner"}
        }
        if damage_origins != {"artificial", "real"}:
            raise ValueError(
                f"{fold.fold_id} does not retain both official damage origins"
            )

    if sorted(observed_inner_counts) != expected_inner_counts:
        raise ValueError("inner-bearing counts must be two in five folds and one in one")


def validate_paderborn_outer_folds(
    folds: tuple[PaderbornOuterFold, ...],
) -> None:
    """Validate the complete 6 x 4 prospective double-unseen manifest."""

    if len(folds) != 24 or len({fold.fold_id for fold in folds}) != 24:
        raise ValueError("Paderborn requires 24 uniquely named outer folds")
    expected_settings = {setting.code for setting in OPERATING_SETTINGS}
    expected_identities = {fold.fold_id for fold in PADERBORN_IDENTITY_FOLDS}
    observed_pairs = {
        (fold.identity_fold_id, fold.held_setting_code) for fold in folds
    }
    expected_pairs = {
        (identity_fold_id, setting_code)
        for identity_fold_id in expected_identities
        for setting_code in expected_settings
    }
    if observed_pairs != expected_pairs:
        raise ValueError("outer folds do not form the complete identity/setting product")

    bearings_by_identity = {
        fold.fold_id: fold.bearing_codes for fold in PADERBORN_IDENTITY_FOLDS
    }
    for fold in folds:
        if fold.identity_fold_id not in expected_identities:
            raise ValueError(f"unknown identity fold: {fold.identity_fold_id}")
        if fold.held_setting_code not in expected_settings:
            raise ValueError(f"unknown operating setting: {fold.held_setting_code}")
        if fold.held_bearing_codes != bearings_by_identity[fold.identity_fold_id]:
            raise ValueError(f"bearing membership changed in {fold.fold_id}")


PADERBORN_OUTER_FOLDS = build_paderborn_outer_folds()
validate_paderborn_outer_folds(PADERBORN_OUTER_FOLDS)
