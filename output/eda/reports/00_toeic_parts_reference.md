# TOEIC Parts Reference

The EdNet dataset is built around TOEIC (Test of English for International Communication), a standardized English proficiency exam. Questions and lectures in the dataset are tagged with `part` values 1-7, corresponding to the exam's structure.

## Exam Structure

### Listening Comprehension (Parts 1-4)


| Part | Name                | Format                                                                  | Choices     | Questions per Bundle |
| ---- | ------------------- | ----------------------------------------------------------------------- | ----------- | -------------------- |
| 1    | Photo Descriptions  | Listen to 4 statements, pick the one that best describes a photo        | 4 (a-d)     | 1                    |
| 2    | Question-Response   | Hear a question, pick the best spoken response                          | **3 (a-c)** | 1                    |
| 3    | Short Conversations | Listen to a conversation between 2-3 speakers, answer questions         | 4 (a-d)     | 3                    |
| 4    | Short Talks         | Listen to a monologue (announcement, voicemail, etc.), answer questions | 4 (a-d)     | 3                    |


### Reading Comprehension (Parts 5-7)


| Part | Name                  | Format                                             | Choices | Questions per Bundle |
| ---- | --------------------- | -------------------------------------------------- | ------- | -------------------- |
| 5    | Incomplete Sentences  | Fill-in-the-blank (grammar/vocabulary)             | 4 (a-d) | 1                    |
| 6    | Text Completion       | Fill in blanks within a longer passage             | 4 (a-d) | 3-4                  |
| 7    | Reading Comprehension | Read single or multiple passages, answer questions | 4 (a-d) | 2-5                  |


## Real Exam vs. EdNet Question Bank

A single TOEIC exam has a fixed number of questions per part:


| Part      | Questions per Exam | Bundles per Exam |
| --------- | ------------------ | ---------------- |
| 1         | 6                  | 6                |
| 2         | 25                 | 25               |
| 3         | 39                 | 13               |
| 4         | 30                 | 10               |
| 5         | 30                 | 30               |
| 6         | 16                 | 4                |
| 7         | 54                 | 15               |
| **Total** | **200**            | **103**          |


EdNet/Santa is a **practice platform**, so its question bank (13,169 questions across 9,534 bundles) is far larger than a single exam — it contains many variants per part for students to practice with. The bundle structure (questions per bundle) still follows the TOEIC format.

## Implications for the Dataset

- **Part 2 has only 3 answer choices** (a/b/c) — this is why `d` is underrepresented in the user answer distribution.
- **Part 5 dominates the question bank** (43%) because each question is standalone (1 per bundle), making them easy to produce at scale.
- **Parts 3, 4, 6, 7 use multi-question bundles** sharing a common passage or audio — this explains the bundle size distribution (3-5 questions per bundle).
- **Audio actions far exceed video actions** in KT4 because Parts 1-4 are listening-based, and the platform delivers audio for these.
- `**part = -1` or `part = 0`** in lectures indicates content not assigned to a specific TOEIC part (general strategy, tips, etc.).

