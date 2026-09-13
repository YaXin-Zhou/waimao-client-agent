from src.application.keyword_expansion import DeepSeekKeywordExpander
from src.domain.task import AcquisitionCriteria


class FakeProvider:
    def __init__(self, data):
        self.data = data
        self.calls = 0

    def generate_json(self, prompt):
        self.calls += 1
        return self.data


def test_expander_validates_deduplicates_and_caches_terms():
    provider = FakeProvider(
        {
            "search_terms": [
                "plastic components",
                "plastic components",
                "https://bad.example",
                "sales@example.com",
                "automotive component supplier",
            ]
        }
    )
    expander = DeepSeekKeywordExpander(provider, max_terms=4)
    criteria = AcquisitionCriteria(product="injection molding", countries=("Germany",))

    assert expander.expand(criteria) == (
        "plastic components",
        "automotive component supplier",
    )
    assert expander.expand(criteria) == expander.expand(criteria)
    assert provider.calls == 1


def test_expander_falls_back_to_empty_on_model_failure():
    class BrokenProvider:
        def generate_json(self, prompt):
            raise RuntimeError("temporary model failure")

    criteria = AcquisitionCriteria(product="CNC machining")
    assert DeepSeekKeywordExpander(BrokenProvider()).expand(criteria) == ()
