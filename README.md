# BigData2026-Assignment2

**Updates are marked with ⭐.**

In this assignment you predict what GitHub users will do in the coming week. For each test
user, you predict which of 6 activities (opening a pull request, pushing code, and so on) the
user will perform during the test week.

This repository contains:

```
assignment2/
+-- README.md                  # download, build the tables, submit
+-- SCHEMA.md                  # every column, explained
+-- train_activity.ipynb       # features, model training, validation, and prediction
+-- requirements.txt          # Python dependencies
+-- scripts/
|   +-- download_gharchive.py  # downloads the historical hourly files
|   +-- preprocess.py          # builds the 8 tables from GH Archive
|   +-- evaluate.py            # checks the format, computes the score
|   +-- cohort.txt             # contains 9,000 anonymized user IDs (read by preprocess.py)
+-- submission/
    +-- test_input.csv         # official test users
    +-- sample_submission.csv  # example output in the correct format
```

## Run the model

From the repository root, use Python 3.11 and install the dependencies. The commands below use
PowerShell. On Linux or macOS, activate the environment with `source .venv/bin/activate` and
copy the manifest with `cp gharchive/hours.json data/hours.json`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

python scripts/download_gharchive.py --raw gharchive --start 2026-10-03T16:00Z --end 2026-11-20T15:00Z
python scripts/preprocess.py --raw gharchive --out data
Copy-Item gharchive/hours.json data/hours.json
python -m jupyter lab train_activity.ipynb
```

In JupyterLab, select the Python kernel and run **Restart Kernel and Run All Cells**. To run
from a terminal, use `python -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=600 train_activity.ipynb`.
Set `ASSIGNMENT_STUDENT_ID` in the shell or edit `STUDENT_ID` in the setup cell to change
the submission filename.

The reproducible archive interval is **Oct. 3, 2026 at 16:00 UTC through Nov. 20, 2026
at 15:00 UTC, exclusive**. This corresponds to Oct. 4 at 00:00 through Nov. 20 at 23:00
in Taiwan. The 1,151 hourly files occupy about 8.1 GiB before preprocessing.
Rerunning the download command reuses completed files and records missing hours in
`hours.json`. Use a dedicated raw data folder for this interval.

The notebook builds time-filtered aggregates across the eight anonymized tables and fits
one L2-regularized logistic regression per activity. Historical snapshots use the same
feature-to-target gap as the final forecast. Training, threshold tuning, and held-out
evaluation use disjoint time windows. The ablation compares 7-day counts, richer temporal
features, and relationship features against the copy-last-week baseline.

The last cell that writes predictions checks the CSV against `submission/test_input.csv`.
The notebook also writes the historical windows, ablation metrics, schema, and framework
diagram under `results/`. With [Graphviz](https://graphviz.org/) installed, render the
schema with `dot -Tsvg results/schema.dot -o results/schema.svg`.

## ⭐ 1. Download the GH Archive files

Download the hourly files of the time period you want from [GH Archive](https://www.gharchive.org)
into your own folder `RAW_DATA_FOLDER`. GH Archive provides one file per hour, named by UTC date
and hour.

For example, based on the command instructions from GH Archive, you can download all the data in
Oct. 2026 using the **GH Archive API**:

```bash
wget -P RAW_DATA_FOLDER https://data.gharchive.org/2026-10-{01..31}-{0..23}.json.gz
```

For more download options, see the GH Archive website.

## ⭐ 2. Build the tables

```bash
python scripts/preprocess.py --raw RAW_DATA_FOLDER --out YOUR_OUTPUT_FOLDER
```

- `RAW_DATA_FOLDER`: your own folder used in Section 1.
- `YOUR_OUTPUT_FOLDER`: your own folder for the tables.

You are required to run our provided preprocessing script before using the data for your model.
The preprocessing script generates the 8 required tables and includes anonymization.

## 3. The tables

| Table | Each row is | Row time |
|---|---|---|
| `Users` | a GitHub user | `first_seen_at` |
| `Repositories` | a repository | `first_seen_at` |
| `PullRequests` | a pull request | `first_seen_at` |
| `Issues` | an issue (the conversation of a pull request is also stored here, with `is_pull_request = true`) | `first_seen_at` |
| `IssueComments` | a comment in an issue or pull request conversation | `created_at` |
| `PRReviews` | a review of a pull request | `first_seen_at` |
| `PRReviewComments` | a comment on specific lines of a pull request's code | `created_at` |
| `Pushes` | a push of commits to a branch or tag | `created_at` |

The **row time** is the time at which a row appears in the data. For a prediction at time t, use
only rows whose row time is before t. Do not filter pull requests, issues or reviews by
`created_at` or `submitted_at`: they can enter the data long after they were created.

**Which users are included.** The tables contain all the activity of 9,000 fixed users (the
*cohort*, marked with `Users.is_cohort = true`), plus the users related to their activity.

**Times** are in UTC (no time zone is stored). Taiwan time is UTC+8.

## 4. Test users and output

⭐ **Test week:** 2026/11/22 00:00 – 11/29 00:00 (Taiwan time)

⭐ **Missing data:** Some hours are missing or incomplete in GH Archive itself. If GH Archive is
missing the data of an activity during the test week, that activity is not scored.

`submission/test_input.csv` lists the test users. Its `UserID` column is `Users.github_user_id`.

Your output is a CSV file with one row per test user, exactly this header, and 1 (the user will
do it) or 0 (the user will not) in each activity column, with no empty cells:

```
UserID,open_pr,open_issue,issue_comment,pr_review,pr_review_comment,push
```

**Example output file:** `submission/sample_submission.csv` (random predictions in the correct
format).

| Column | 1 means that during the test week the user ... |
|---|---|
| `open_pr` | opens a pull request |
| `open_issue` | opens an issue (not a pull request) |
| `issue_comment` | comments in an issue or pull request conversation |
| `pr_review` | submits a review of a pull request |
| `pr_review_comment` | comments on specific lines of a pull request's code |
| `push` | pushes commits to a branch or tag |

**Checking and scoring.** A file with a format error is not scored.

```bash
# Check the format of your output file
python scripts/evaluate.py --pred output_{studentID}.csv --input submission/test_input.csv

# Score your predictions for a validation week against your own answer file (same format)
python scripts/evaluate.py --pred YOUR_PREDICTION_FILE --truth YOUR_ANSWER_FILE
```

**Scoring.** F1 for each activity; `Score = (macro-F1 + micro-F1) / 2`.

**Reference scores.** These are the scores of five baseline methods that we tested on the
week of 2026/09/27 – 10/04.

| Method | macro-F1 | micro-F1 | Score |
|---|---|---|---|
| Random | 19.77% | 22.74% | 21.26% |
| Predict all 0 | 0.00% | 0.00% | 0.00% |
| Copy last week | 43.01% | 56.20% | 49.61% |
| GNN without time encoding | 22.80% | 48.61% | 35.70% |
| GNN with time encoding | 50.90% | 58.74% | 54.82% |

- **Copy last week**: for each activity, 1 if the user did it in the 7 days before the
  prediction time, otherwise 0.
- **GNN**: a graph neural network on the 8 tables, as in the
  [RelBench](https://relbench.stanford.edu) examples. The version with time encoding also
  tells the model how long before the prediction time each row happened.

## Data Source

The data used in this assignment is sourced from [GH Archive](https://www.gharchive.org), a
publicly available archive of GitHub events. This assignment is intended for educational
purposes within this course.
