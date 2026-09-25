from app.records import format_japanese


def test_japanese_separator_spaces_only():
    assert format_japanese('今日は よろしく お願いします 。') == '今日はよろしくお願いします。'
    assert format_japanese('Microsoft Teams で 会議します。') == 'Microsoft Teams で会議します。'


def test_formatting_does_not_correct_recognition_or_remove_newlines():
    assert format_japanese('あいうえを。\nロープ') == 'あいうえを。\nロープ'
