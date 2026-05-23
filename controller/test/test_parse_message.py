import pytest

from controller.src.mqtt_client import MessageParseError, parse_message


def test_heartbeat() -> None:
    node_id, action, team = parse_message("STA01H0")
    assert node_id == "STA01"
    assert action == "H"
    assert team == 0


def test_activation_team_A() -> None:
    node_id, action, team = parse_message("DET01AA")
    assert node_id == "DET01"
    assert action == "A"
    assert team == 1


def test_activation_team_D() -> None:
    node_id, action, team = parse_message("DET01AD")
    assert node_id == "DET01"
    assert action == "A"
    assert team == 4


def test_activation_team_numeric_1() -> None:
    _, _, team = parse_message("DET01A1")
    assert team == 1


def test_activation_team_numeric_4() -> None:
    _, _, team = parse_message("DET01A4")
    assert team == 4


def test_invalid_length() -> None:
    with pytest.raises(MessageParseError, match="消息长度错误"):
        parse_message("SHORT")


def test_invalid_action_type() -> None:
    with pytest.raises(MessageParseError, match="无效的动作类型"):
        parse_message("DET01X0")


def test_heartbeat_extra_not_zero() -> None:
    with pytest.raises(MessageParseError, match="心跳消息 extra_info 必须为"):
        parse_message("STA01HX")


def test_invalid_team() -> None:
    with pytest.raises(MessageParseError, match="无效的队伍编号"):
        parse_message("DET01AE")


def test_empty_string() -> None:
    with pytest.raises(MessageParseError):
        parse_message("")


def test_activation_boundary_teams() -> None:
    _, _, team_A = parse_message("DET01AA")
    _, _, team_D = parse_message("DET01AD")
    assert team_A == 1
    assert team_D == 4
