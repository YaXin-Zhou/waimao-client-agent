import pytest

from src.domain.custom_research import (
    BusinessOffering,
    ResearchFieldDefinition,
    ResearchFieldType,
    ResearchFieldValue,
)
from src.domain.research import CustomerType, EvidenceStatus, ResearchResult
from src.domain.task import AcquisitionCriteria, AcquisitionTask
from src.infrastructure.sqlite_repositories import SQLiteResearchRepository, SQLiteTaskRepository


def test_custom_configuration_is_serializable_and_evidence_aware():
    offering = BusinessOffering(
        "CNC machining", "cnc_machining", "Low-volume precision parts", ("CNC", "machining")
    )
    field = ResearchFieldDefinition(
        "Purchasing contact",
        "purchasing_contact",
        "Public buyer or sourcing contact",
        ("purchasing",),
    )
    criteria = AcquisitionCriteria(
        product="configured services",
        business_offerings=(offering,),
        research_fields=(field,),
    )

    assert criteria.business_offerings[0].to_dict()["keywords"] == ["CNC", "machining"]
    assert criteria.research_fields[0].to_dict()["evidence_required"] is True


def test_duplicate_custom_keys_are_rejected():
    item = BusinessOffering("Injection molding", "injection_molding", keywords=("mold",))
    with pytest.raises(ValueError, match="keys must be unique"):
        AcquisitionCriteria(product="services", business_offerings=(item, item))


def test_field_types_and_values_are_validated():
    field = ResearchFieldDefinition(
        "Needs service", "needs_service", field_type=ResearchFieldType.BOOLEAN
    )
    value = ResearchFieldValue("true", "verified", 0.9, ("https://example.com",))
    assert field.field_type is ResearchFieldType.BOOLEAN
    assert value.to_dict()["status"] == "verified"

    with pytest.raises(ValueError):
        ResearchFieldDefinition("Bad", "Bad-Key")
    with pytest.raises(ValueError):
        ResearchFieldValue("guess", "unknown", 1.1)


def test_task_and_research_custom_fields_round_trip(tmp_path):
    criteria = AcquisitionCriteria(
        "configured services",
        business_offerings=(BusinessOffering("CNC", "cnc_service", keywords=("CNC",)),),
        research_fields=(
            ResearchFieldDefinition("Buyer role", "buyer_role", keywords=("purchasing",)),
        ),
    )
    task = AcquisitionTask.create("configured task", criteria)
    database = tmp_path / "acquisition.db"
    SQLiteTaskRepository(database).save(task)
    loaded = SQLiteTaskRepository(database).get(task.id)
    assert loaded.criteria.research_fields[0].key == "buyer_role"

    report = ResearchResult(
        "Example",
        "Manufacturer",
        CustomerType.MANUFACTURER,
        ("parts",),
        "Germany",
        0.8,
        "https://example.com",
        EvidenceStatus.SUFFICIENT,
        custom_fields={
            "buyer_role": ResearchFieldValue(
                "Sourcing Manager", "verified", 0.8, ("https://example.com/team",)
            )
        },
    )
    SQLiteResearchRepository(database).save(task.id, "example.com", report)
    restored = SQLiteResearchRepository(database).get(task.id, "example.com")
    assert restored.custom_fields["buyer_role"].status == "verified"
