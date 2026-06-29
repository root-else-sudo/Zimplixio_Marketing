import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'execution'))

from posts_generate import (
    pick_research_query_indices,
    pick_outcome_pattern_by_index,
    extract_hook,
    build_system_prompt,
    OUTCOME_PATTERNS,
    TAVILY_RESEARCH_QUERIES,
)


class TestPickResearchQueryIndices:
    def test_starts_at_zero_when_run_count_zero(self):
        result = pick_research_query_indices(0, 10)
        assert result == [0, 1]

    def test_advances_by_run_count(self):
        result = pick_research_query_indices(4, 10)
        assert result == [4, 5]

    def test_wraps_around_at_end_of_list(self):
        result = pick_research_query_indices(9, 10)
        assert result == [9, 0]

    def test_wraps_both_when_near_end(self):
        result = pick_research_query_indices(8, 10)
        assert result == [8, 9]

    def test_works_with_real_query_list_length(self):
        n = len(TAVILY_RESEARCH_QUERIES)
        result = pick_research_query_indices(n - 1, n)
        assert result[0] == n - 1
        assert result[1] == 0


class TestPickOutcomePatternByIndex:
    def test_picks_first_pattern_when_index_zero(self):
        context = {}
        pattern = pick_outcome_pattern_by_index(context)
        assert pattern == OUTCOME_PATTERNS[0]

    def test_increments_index_in_context(self):
        context = {}
        pick_outcome_pattern_by_index(context)
        assert context['outcome_pattern_index'] == 1

    def test_picks_second_pattern_when_index_one(self):
        context = {'outcome_pattern_index': 1}
        pattern = pick_outcome_pattern_by_index(context)
        assert pattern == OUTCOME_PATTERNS[1]

    def test_wraps_around_after_last_pattern(self):
        n = len(OUTCOME_PATTERNS)
        context = {'outcome_pattern_index': n}
        pattern = pick_outcome_pattern_by_index(context)
        assert pattern == OUTCOME_PATTERNS[0]
        assert context['outcome_pattern_index'] == n + 1

    def test_each_call_advances_index(self):
        context = {}
        for i in range(len(OUTCOME_PATTERNS)):
            pattern = pick_outcome_pattern_by_index(context)
            assert pattern == OUTCOME_PATTERNS[i]

    def test_full_cycle_wraps_back_to_start(self):
        n = len(OUTCOME_PATTERNS)
        context = {'outcome_pattern_index': n - 1}
        # Last pattern
        last = pick_outcome_pattern_by_index(context)
        assert last == OUTCOME_PATTERNS[n - 1]
        # Next call wraps to first
        first = pick_outcome_pattern_by_index(context)
        assert first == OUTCOME_PATTERNS[0]


class TestExtractHook:
    def test_returns_first_non_empty_line(self):
        post = "\n\nYour dispatch runs on a spreadsheet.\n\nHere is more content."
        assert extract_hook(post) == "Your dispatch runs on a spreadsheet."

    def test_strips_whitespace(self):
        post = "   First line with spaces.   \nSecond line."
        assert extract_hook(post) == "First line with spaces."

    def test_truncates_at_150_chars(self):
        long_line = "A" * 200
        post = f"{long_line}\nSecond line."
        result = extract_hook(post)
        assert len(result) == 150

    def test_returns_empty_string_for_blank_post(self):
        assert extract_hook("") == ""
        assert extract_hook("   \n\n   ") == ""

    def test_handles_leading_blank_lines(self):
        post = "   \n\n   \n\nContent here"
        assert extract_hook(post) == "Content here"


class TestBuildSystemPrompt:
    def test_returns_base_when_no_recent_hooks(self):
        result = build_system_prompt([])
        assert 'AVOID REPEATING' not in result

    def test_injects_avoid_section_when_hooks_present(self):
        hooks = ["Your dispatch runs on a spreadsheet.", "Nobody knows the numbers until month end."]
        result = build_system_prompt(hooks)
        assert 'AVOID REPEATING' in result
        assert hooks[0] in result
        assert hooks[1] in result

    def test_uses_only_last_five_hooks(self):
        hooks = [f"Hook number {i}" for i in range(10)]
        result = build_system_prompt(hooks)
        assert "Hook number 9" in result
        assert "Hook number 4" not in result

    def test_base_content_always_present(self):
        result = build_system_prompt(["some hook"])
        assert "AVOID REPEATING" in result
        assert "- some hook" in result
        assert "HOOK" in result
