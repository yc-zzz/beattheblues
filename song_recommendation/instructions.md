I want to revamp @song_recommendation/train_ml.py, specifically, the generate_description function. the diagnostic tests reveal that a problem lies with the numeric columns (e.g dance, acoustic), with their low correlation scores. It seems like the model is unable to use this information to generate better predictions, and I believe it could be because of how deterministic and lossy the descriptions are with regard to these columns -- one of 4 adjectives is attached to the columns (e.g very dance, quite happy), there's very little linguistic variety that allows for meaningful differentiation along these dimensions. 

For every numeric column (e.g dance, acoustic, aggressive, timbre (dark/bright), etc.), i want to generate a set of more detailed descriptions. There should be roughly 10 bins with slight overlap, where 0 and 1 are near complete opposites. 

For example, happy:
Range	Possible language
0.00–0.15	deeply somber, distinctly unhappy, gloomy
0.08–0.25	melancholic, downcast, rather bleak
0.18–0.35	subdued, somewhat melancholy, low-spirited
0.28–0.45	restrained, slightly downbeat, not especially cheerful
0.38–0.55	emotionally neutral, balanced in mood
0.48–0.65	mildly positive, pleasant, gently upbeat
0.58–0.75	cheerful, positive, upbeat
0.68–0.85	bright, buoyant, feel-good
0.78–0.95	joyful, very cheerful, uplifting, sunny
0.88–1.00	exuberant, euphoric, intensely joyful

Then, generate 4 template descriptions -- each song would then have 4 descriptions based on these templates. Every template should mention EVERY column (across NUMERIC_COLUMNS, CATEGORICAL_COLUMNS, MIREX_DESCRIPTIONS, GENRE_NAMES, see @train_ml.py), meaning that there should be no omission of information. For every column mention, instead of adding all possible words belonging to that category, it would just select a word. This should also apply to MIREX descriptions -- currently, it adds all words associated to a MIREX group, but I want to change it to sample just one word from that group. 

To give a concrete example for the above, I may have a description that says "A {happy_adjective} track with a {party_adjective} character...". If the score for happy is 0.80, my choices lie in the 0.68-0.85 and the 0.78-0.95 range. I should choose a single word from these 2 categories. Here, {happy_adjective} might be "sunny". Another description of the same song may include {happy_adjective}, but the sampled {happy_adjective} could be different but still within the correct range, such as "buoyant". 

An example that ChatGPT gave, to illustrate how different sentence structures can lead to varied descriptions: 
<example>
- Template A — descriptive

A bright, upbeat rock track with a lively, dance-friendly character. It feels energetic rather than relaxed, with little sense of sadness. The sound is predominantly electronic and fairly bright...

- Template B — recommendation/query style

Rock music with an upbeat, feel-good mood, good for a lively social setting. Looking for something danceable and energetic rather than calm or melancholic...

- Template C — analytical

The track has a strongly positive emotional character with relatively little sadness. Its energy leans toward aggressive and dance-oriented, while the production is more electronic than acoustic...

- Template D — concise

Upbeat, danceable electronic rock with a bright sound, lively party energy and little sadness. Vocal track with...
</example>

I also want experiment reproducibility. Seeds should be derived from (random_state, song_id, template_id, column_name), to ensure that the same seed produces the same descriptions. 

It is important that the train-test splits are done before the song descriptions are generated. This effectively means that there should not be a case where the same song appears on both the train and the test splits (e.g for a song, vector for description A appears in the train set, vector for description C appears in the test set). 

Finally, some checks: 
- unique(train_song_ids) ∩ unique(test_song_ids) = ∅
- len(train_descriptions) = 4 × n_train_songs
- len(test_descriptions)  = 4 × n_test_songs
- each train song → exactly 4 descriptions
- each test song  → exactly 4 descriptions
- each description → exactly one correctly aligned target vector
- every description represents every numeric + categorical feature