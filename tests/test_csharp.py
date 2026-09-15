from modernizer_agent.csharp import CSharpParser


def test_extracts_class_and_method():
    result = CSharpParser().parse('namespace Demo; public class PriceService { public decimal Total(Order o) { return 1m; } }')
    names = {s["name"] for s in result.symbols}
    assert "PriceService" in names
    assert "Total" in names
