"""
test_score.py -- Verify scoring logic against a hardcoded 10-row sample.

Run:
    python test_score.py
"""

import csv
import io
import sys
from score_leads import score_row, tier

# ---------------------------------------------------------------------------
# Test cases: (first, last, company, position, expected_score, expected_tier)
# ---------------------------------------------------------------------------
TEST_CASES = [
    # "medtech"=+2 (industry_high), "materials" in combined=+1 (industry_med),
    # "engineer"=+2 + "materials"=+2 in title_high => 7 -> Top
    ("Alice", "Chen",    "MedTech Innovations",     "Senior Materials Engineer",        7, "Top"),

    # "life science" and "life sciences" both match in INDUSTRY_HIGH (+4 total),
    # "principal"=+2 + "scientist"=+2 in title_high => 8 -> Top
    ("Bob",   "Sharma",  "BioGen Life Sciences",    "Principal Scientist",              8, "Top"),

    # "fertility"=+2 (industry_high), "r&d"=+1 (industry_med),
    # "r&d"=+2 in title_high => 6 -> Top (note: "director" alone is not in title_high)
    ("Carol", "Lee",     "Fertility Clinic Inc",    "R&D Director",                     6, "Top"),

    # "plastics"=+1 (industry_med), "operations"=+1 + "manager"=+1 (title_med) => 3 -> Strong
    ("Dave",  "Kim",     "National Plastics Co",    "Operations Manager",               3, "Strong"),

    # "aerospace"=+1 + "polymer"=+1 (industry_med), "researcher"=+2 (title_high) => 5 -> Top
    # "polymers" also matches via "polymer group" substring... wait no. "polymer" is the keyword.
    # "Aerospace Polymer Group" contains both "aerospace" and "polymer" => +2 industry_med
    # title "Researcher" => "researcher"=+2, "research" in combined=+1 (industry_med) => 5 -> Top
    ("Eva",   "Muller",  "Aerospace Polymer Group", "Researcher",                       5, "Top"),

    # No industry keywords, "engineer" in title_high=+2 => 2 -> Strong
    ("Frank", "Osei",    "Acme Software LLC",       "Software Engineer",                2, "Strong"),

    # "pharma"=+2 (industry_high) but recruiter hard cap kicks in -> 0 -> Skip
    ("Grace", "Patel",   "Pharma Dynamics",         "Technical Recruiter",              0, "Skip"),

    # "consumer goods"=+1 (industry_med), "manager"=+1 (title_med),
    # "social media"=-1 + "marketing"=-1 (title_neg) => 0 -> Skip
    ("Henry", "Tran",    "Consumer Goods Corp",     "Social Media Marketing Manager",   0, "Skip"),

    # No relevant keywords => 0 -> Skip
    ("Irene", "Gomez",   "Downtown Bakery",         "Barista",                          0, "Skip"),

    # "chemical"=+1 (industry_med), "engineer"=+2 + "quality"=+2 (title_high) => 5 -> Top
    # (Note: "ChemForm" does not contain "chemical" as a substring? Let me check: "chemform" vs "chemical" -- no match)
    # Actually "ChemForm Solutions" lower = "chemform solutions", "chemical" not in there.
    # "quality engineer" lower = "quality engineer", "chemical" not in position either.
    # So: "engineer"=+2 + "quality"=+2 in title => 4 -> Top
    ("James", "Wu",      "ChemForm Solutions",      "Quality Engineer",                 4, "Top"),

    # --- Real-world false positive verification cases ---

    # WILLWAY GLOBAL: "executive search" in title triggers recruiter hard cap -> 0 -> Skip
    # (Full real title: "President & CEO | Executive Search | Pharmaceutical, Medical Device, Life Sciences")
    ("Josephine", "Belfield",  "WILLWAY GLOBAL",                 "President & CEO | Executive Search | Pharmaceutical, Medical Device, Life Sciences & Healthcare", 0, "Skip"),

    # TekWissen: "recruitment" in title triggers recruiter hard cap -> 0 -> Skip
    ("Purandhar", "Rayudu",    "TekWissen",                      "Assistant Manager - Pharma, Biotech Recruiting",  0, "Skip"),

    # "Undergraduate Student Researcher": student keyword -> hard cap at 1 -> Weak
    ("Camille",   "White",     "UCLA",                           "Undergraduate Student Researcher",                1, "Weak"),

    # Raytheon doesn't contain "defense" or "aerospace" explicitly.
    # "materials"=+1 (industry_med). "principal"=+2, "materials"=+2, "engineer"=+2 (title_high).
    # No penalties. => 7 -> Top (tier unchanged from before the fix)
    ("Krystal",   "Cunningham","Raytheon",                       "Principal Materials and Process Engineer",         7, "Top"),

    # "lab" substring matches "laboratory" (+1), "laboratory"=+1, "research"=+1, "materials"=+1
    # (industry_med = +4). "materials"=+2, "engineer"=+2 (title_high = +4). No penalties. => 8 -> Top
    ("SungJoon",  "Lee",       "U.S. Naval Research Laboratory", "Materials Research Engineer",                     8, "Top"),
]


def run_tests():
    passed = 0
    failed = 0

    print(f"\n{'='*72}")
    print(f"  score_leads.py -- Unit Tests")
    print(f"{'='*72}")
    print(f"  {'#':<3} {'Name':<14} {'Company':<28} {'Title':<30} {'Exp':>4} {'Got':>4} {'Tier':<8} {'OK?'}")
    print(f"  {'-'*3} {'-'*14} {'-'*28} {'-'*30} {'-'*4} {'-'*4} {'-'*8} {'-'*4}")

    for i, (first, last, company, position, exp_score, exp_tier) in enumerate(TEST_CASES, 1):
        got_score = score_row(company, position)
        got_tier = tier(got_score)

        score_ok = got_score == exp_score
        tier_ok = got_tier == exp_tier
        ok = score_ok and tier_ok

        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1

        name = f"{first} {last}"
        print(f"  {i:<3} {name:<14} {company[:27]:<28} {position[:29]:<30} {exp_score:>4} {got_score:>4} {got_tier:<8} {status}")

        if not score_ok:
            print(f"      ^^^ Score mismatch: expected {exp_score}, got {got_score}")
        if not tier_ok:
            print(f"      ^^^ Tier mismatch: expected {exp_tier}, got {got_tier}")

    print(f"\n  Results: {passed}/{len(TEST_CASES)} passed", end="")
    if failed:
        print(f"  ({failed} FAILED)")
    else:
        print("  -- all good")
    print()

    return failed


if __name__ == "__main__":
    failures = run_tests()
    sys.exit(1 if failures else 0)
