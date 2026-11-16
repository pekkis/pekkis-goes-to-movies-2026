# The survey's scales: bipolar questions and the table of means

A note for the WS4 presentation's quantitative part. The full analysis is in [survey-2026-11.md](survey-2026-11.md).

## What the assignment asks

From the course's instructions:

- WS3: "You need to conduct both the Focus Group Interview and create a survey **(bipolar questions)**."
- WS4: "Show your UX survey quantitative collected data (**table of mean values - Descriptive Statistics**); see video instructions."

## What a bipolar question is

A **bipolar question** (a semantic differential) puts two opposite words at the ends of a scale; the respondent marks a point between them. The middle is neutral.

```
Complicated   ○ ○ ○ ○ ○ ○ ○   Easy
Boring        ○ ○ ○ ○ ○ ○ ○   Exciting
Slow          ○ ○ ○ ○ ○ ○ ○   Fast
```

Answers are usually coded −3 … +3. The standard set for UX is the **UEQ** (User Experience Questionnaire, 26 pairs) or its short version **UEQ-S** (8 pairs), filled in after using the product. That's our assumption of what the course means; the course video would confirm it.

A **unipolar** question goes from "none" to "a lot" instead, e.g. "not at all useful … extremely useful".

## What a table of means is

Descriptive statistics, one row per question:

- **n**: how many answered;
- **mean**: the average;
- **SD** (standard deviation): how much the answers vary. Small means people agreed; large means they split.

Median, minimum and maximum are often added.

## What our survey has

The survey has two rating-scale questions (1–5) and otherwise multiple choice and open answers:

| Item                                                                                                                 | Kind of scale                                | n   | Mean | SD   |
| -------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- | --- | ---- | ---- |
| How satisfied are you with the websites or apps you use now? (very dissatisfied … very satisfied)                    | **Bipolar**: opposites with a neutral middle | 21  | 3.00 | 0.84 |
| How useful would it be to see showtimes from different Finnish cinemas in one place? (not at all … extremely useful) | Unipolar                                     | 22  | 3.73 | 0.83 |

For the statistics, a 1–5 unipolar scale and a bipolar one are handled the same way: a mean and SD per item. The difference that matters is **what was measured**:

- **UEQ-style bipolar pairs** rate **the product** after using it: is our prototype easy or complicated, clear or confusing?
- **Our survey** measures **the current situation and the need**: how satisfied people are with today's sites, and how useful one place would be. Nobody rated the prototype on a scale; feedback on the prototype is qualitative, from the [focus group](focus-group-2026-11-10.md).

## How to present it

- Call them "rating scales (1–5)" and show the table above. If asked: satisfaction is on a bipolar scale, and the survey measured the need, not the prototype.
- If bipolar items about the prototype are wanted, the quickest addition is the **UEQ-S** (8 pairs) sent with a link to the prototype (`/fi/haku`). Its scores can be computed from the UEQ's own spreadsheet tool. The data would need a few days to collect.
