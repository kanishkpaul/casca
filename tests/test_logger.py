from casca.logger import RunLogger


def test_runs_started_in_the_same_second_get_their_own_directory(tmp_path):
    assert RunLogger(tmp_path).run_dir != RunLogger(tmp_path).run_dir
