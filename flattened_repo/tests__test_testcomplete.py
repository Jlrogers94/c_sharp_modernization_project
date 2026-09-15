from modernizer_agent.testcomplete import parse_testcomplete_file


def test_extracts_aliases():
    text = 'function test(){ Aliases.MyApp.OrderForm.SaveButton.Click(); Sys.Process("app"); }'
    tests = parse_testcomplete_file("Tests/Order.js", text)
    assert tests
    assert "Aliases.MyApp.OrderForm.SaveButton" in tests[0]["aliases"]
