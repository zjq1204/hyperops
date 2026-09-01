import hashlib
import re
import secrets
import string
import unicodedata
from dataclasses import dataclass

ALLOWED_TEMPLATE_VARIABLES = {
    "prefix",
    "user",
    "business_name",
    "project",
    "environment",
    "purpose",
    "suffix",
}
SLUG_PATTERN = re.compile(r"[^a-z0-9]+")
SUFFIX_PATTERN = re.compile(r"[a-z0-9]{8}")
BUCKET_NAME_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]")
SUFFIX_ALPHABET = string.ascii_lowercase + string.digits


class BucketNamingError(ValueError):
    pass


@dataclass(frozen=True)
class BucketNameCandidate:
    name: str
    suffix: str


def _stable_hash(value, length=8):
    payload = str(value or "").strip().casefold()
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:length]


def _slug(value):
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = SLUG_PATTERN.sub("-", ascii_value).strip("-")
    return slug or f"x{_stable_hash(value)}"


def generate_suffix():
    return "".join(secrets.choice(SUFFIX_ALPHABET) for _index in range(8))


def validate_naming_template(template):
    if not isinstance(template, str) or not template.strip():
        raise BucketNamingError("TEMPLATE_REQUIRED")
    variables = []
    try:
        for _literal, field_name, format_spec, conversion in string.Formatter().parse(
            template
        ):
            if field_name is None:
                continue
            if format_spec or conversion:
                raise BucketNamingError("TEMPLATE_FORMAT_UNSUPPORTED")
            variables.append(field_name)
    except ValueError as exc:
        raise BucketNamingError("TEMPLATE_INVALID") from exc
    if set(variables) - ALLOWED_TEMPLATE_VARIABLES:
        raise BucketNamingError("UNKNOWN_TEMPLATE_VARIABLE")
    if "suffix" not in variables:
        raise BucketNamingError("SUFFIX_REQUIRED")
    return tuple(variables)


def render_bucket_name(
    *,
    template,
    prefix,
    user,
    business_name,
    project,
    environment,
    purpose,
    suffix,
):
    validate_naming_template(template)
    if not isinstance(suffix, str) or not SUFFIX_PATTERN.fullmatch(suffix):
        raise BucketNamingError("SUFFIX_INVALID")

    values = {
        "prefix": _slug(prefix),
        "user": _slug(user),
        "business_name": _slug(business_name),
        "project": _slug(project),
        "environment": _slug(environment),
        "purpose": _slug(purpose),
        "suffix": suffix,
    }
    rendered = template.format(**values).lower()
    if len(rendered) > 63:
        raise BucketNamingError("BUCKET_NAME_TOO_LONG")
    if len(rendered) < 3:
        raise BucketNamingError("BUCKET_NAME_TOO_SHORT")
    if not rendered.isascii() or not BUCKET_NAME_PATTERN.fullmatch(rendered):
        raise BucketNamingError("BUCKET_NAME_INVALID")
    return rendered


def generate_bucket_name_candidate(**render_values):
    suffix = generate_suffix()
    return BucketNameCandidate(
        name=render_bucket_name(suffix=suffix, **render_values),
        suffix=suffix,
    )


def _candidate_for_suffix(suffix, render_values):
    return BucketNameCandidate(
        name=render_bucket_name(suffix=suffix, **render_values),
        suffix=suffix,
    )


def _initial_bucket_name_candidate(initial_suffix, initial_candidate, render_values):
    if (initial_suffix is None) == (initial_candidate is None):
        raise BucketNamingError("INITIAL_BUCKET_NAME_REQUIRED")
    if initial_candidate is None:
        return _candidate_for_suffix(initial_suffix, render_values)
    if not isinstance(initial_candidate, BucketNameCandidate):
        raise BucketNamingError("INITIAL_CANDIDATE_INVALID")
    expected = _candidate_for_suffix(initial_candidate.suffix, render_values)
    if initial_candidate != expected:
        raise BucketNamingError("INITIAL_CANDIDATE_MISMATCH")
    return initial_candidate


def _generate_fresh_candidate(render_values, used_suffixes):
    for _generation_attempt in range(32):
        suffix = generate_suffix()
        if suffix not in used_suffixes:
            return _candidate_for_suffix(suffix, render_values)
    raise BucketNamingError("SUFFIX_GENERATION_EXHAUSTED")


def create_bucket_with_unique_name(
    *,
    create_callback,
    initial_suffix=None,
    initial_candidate=None,
    **render_values,
):
    from object_storage.services.provider_errors import ObjectStorageProviderError

    candidate = _initial_bucket_name_candidate(
        initial_suffix,
        initial_candidate,
        render_values,
    )
    used_suffixes = {candidate.suffix}
    for attempt in range(4):
        try:
            return create_callback(candidate)
        except ObjectStorageProviderError as exc:
            if exc.error_code != "BUCKET_NAME_CONFLICT":
                raise
            if attempt == 3:
                raise
            candidate = _generate_fresh_candidate(render_values, used_suffixes)
            used_suffixes.add(candidate.suffix)


def remaining_business_name_length(template, context, suffix):
    variables = validate_naming_template(template)
    if not isinstance(suffix, str) or not SUFFIX_PATTERN.fullmatch(suffix):
        raise BucketNamingError("SUFFIX_INVALID")
    occurrences = variables.count("business_name")
    if occurrences == 0:
        return 0
    values = {
        name: _slug(context.get(name, ""))
        for name in ALLOWED_TEMPLATE_VARIABLES - {"business_name", "suffix"}
    }
    values.update({"business_name": "", "suffix": suffix})
    fixed_length = len(template.format(**values))
    return max(0, (63 - fixed_length) // occurrences)
