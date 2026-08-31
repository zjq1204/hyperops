import hashlib
import re
import string
import unicodedata

ALLOWED_TEMPLATE_VARIABLES = {
    "tenant",
    "user",
    "project",
    "environment",
    "purpose",
    "suffix",
}
SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


class BucketNamingError(ValueError):
    pass


def _stable_hash(*values, length=8):
    payload = "\x1f".join(str(value or "").strip().casefold() for value in values)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:length]


def _slug(value, *, fallback_seed):
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = SLUG_PATTERN.sub("-", ascii_value).strip("-")
    return slug or f"x{_stable_hash(fallback_seed)}"


def validate_naming_template(template):
    if not isinstance(template, str) or not template.strip():
        raise BucketNamingError("TEMPLATE_REQUIRED")
    variables = []
    try:
        parsed = string.Formatter().parse(template)
        for _literal, field_name, format_spec, conversion in parsed:
            if field_name is None:
                continue
            if format_spec or conversion:
                raise BucketNamingError("TEMPLATE_FORMAT_UNSUPPORTED")
            variables.append(field_name)
    except ValueError as exc:
        raise BucketNamingError("TEMPLATE_INVALID") from exc
    unknown = set(variables) - ALLOWED_TEMPLATE_VARIABLES
    if unknown:
        raise BucketNamingError("UNKNOWN_TEMPLATE_VARIABLE")
    if "suffix" not in variables:
        raise BucketNamingError("SUFFIX_REQUIRED")
    return tuple(variables)


def render_bucket_name(
    *, tenant, membership, project, environment, purpose, template=None
):
    selected_template = template or tenant.bucket_naming_template
    validate_naming_template(selected_template)
    suffix = _stable_hash(
        tenant.code,
        membership.feishu_open_id,
        project,
        environment,
        purpose,
    )
    values = {
        "tenant": _slug(tenant.code, fallback_seed=tenant.code),
        "user": _slug(
            membership.display_name,
            fallback_seed=membership.feishu_open_id,
        ),
        "project": _slug(project, fallback_seed=project),
        "environment": _slug(environment, fallback_seed=environment),
        "purpose": _slug(purpose, fallback_seed=purpose),
        "suffix": suffix,
    }
    rendered = selected_template.format(**values)
    normalized = SLUG_PATTERN.sub("-", rendered.lower()).strip("-")
    if len(normalized) > 63:
        prefix_length = 63 - len(suffix) - 1
        normalized = f"{normalized[:prefix_length].rstrip('-')}-{suffix}"
    if len(normalized) < 3:
        normalized = f"obj-{suffix}"
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", normalized):
        raise BucketNamingError("RENDERED_NAME_INVALID")
    return normalized
