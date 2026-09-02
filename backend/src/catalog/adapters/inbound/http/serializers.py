"""DRF serializers for the catalog HTTP adapter.

Serializes the application ProductView read model (a dataclass) to JSON. Decimal
fields render as strings (e.g. "60.00").
"""

from __future__ import annotations

from rest_framework import serializers


class ProductViewSerializer(serializers.Serializer):
    wb_id = serializers.IntegerField()
    name = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    sale_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    discount_abs = serializers.DecimalField(max_digits=10, decimal_places=2)
    discount_pct = serializers.DecimalField(max_digits=6, decimal_places=2)
    rating = serializers.DecimalField(max_digits=2, decimal_places=1)
    reviews_count = serializers.IntegerField()
    query = serializers.CharField(allow_null=True)
    updated_at = serializers.DateTimeField(allow_null=True)


class ParseJobSerializer(serializers.Serializer):
    task_id = serializers.CharField()
    query = serializers.CharField()
    status = serializers.CharField()
    created = serializers.IntegerField()
    updated = serializers.IntegerField()
    collected_count = serializers.IntegerField()
    error = serializers.CharField(allow_null=True)
    finished_at = serializers.DateTimeField(allow_null=True)


# --- Response envelopes ---------------------------------------------------
#
# These describe shapes the views assemble by hand. Without them the schema
# generator falls back to an empty body, which produces a specification that
# validates nothing while looking complete.


class ErrorSerializer(serializers.Serializer):
    """The `{"detail": ...}` body the shared exception handler returns.

    Not the only error body in the API: DRF answers its own serializer
    validation with a field-keyed map instead, and the handler passes that
    through untouched. The docstring here used to claim this shape covered
    "every error path", which is what a contract test disproved — see
    `FIELD_ERRORS_SCHEMA` below and `VALIDATION_ERROR_RESPONSE`.
    """

    detail = serializers.CharField()


#: DRF's own validation body: `{"username": ["Обязательное поле."]}`. Declared
#: as a raw schema because the shape is a free-form map, which a Serializer
#: expresses as a named field rather than as `additionalProperties`.
FIELD_ERRORS_SCHEMA: dict[str, object] = {
    "type": "object",
    # Both shapes occur: DRF wraps its own messages in a list, while code that
    # raises `ValidationError({"username": "already taken"})` by hand leaves the
    # string bare. Declaring only the list form is what a contract run caught.
    "additionalProperties": {
        "oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]
    },
    "description": "Field-keyed validation errors, as DRF renders them.",
}

#: What a 400 actually looks like on the endpoints that run a DRF serializer:
#: either envelope, depending on which layer rejected the request. Both are
#: declared because a client that expects only the first reads a field-keyed
#: body as a missing `detail` and shows the user nothing.
VALIDATION_ERROR_SCHEMA: dict[str, object] = {
    # `anyOf`, not `oneOf`: `{"detail": "..."}` satisfies both branches at once,
    # since the field-keyed map allows a bare string value. Under `oneOf` that
    # is a validation failure ("valid under more than one"), so the union
    # rejected the single most common error body in the API.
    "anyOf": [
        {
            "type": "object",
            "properties": {"detail": {"type": "string"}},
            "required": ["detail"],
        },
        FIELD_ERRORS_SCHEMA,
    ]
}


class ProductPageSerializer(serializers.Serializer):
    """`GET /api/products/` — DRF's page envelope, assembled manually."""

    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = ProductViewSerializer(many=True)


class ParseEnqueuedSerializer(serializers.Serializer):
    """`POST /api/parse/` — 202 with the accepted job, not the finished one."""

    task_id = serializers.CharField()
    query = serializers.CharField()
    status = serializers.CharField()


class ParseRequestSerializer(serializers.Serializer):
    """`POST /api/parse/` body. Validated by hand in the view, described here."""

    query = serializers.CharField(max_length=200)
    max_pages = serializers.IntegerField(
        required=False,
        # The view reads None and "" as "use the server default", so a schema
        # that forbids null describes a rejection the API does not perform.
        allow_null=True,
        min_value=1,
        max_value=20,
        help_text="Defaults to the server setting.",
    )
