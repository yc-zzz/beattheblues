# Experiment 4 

## Experiment 3 Diagnostics 
Generally, the run was a step forward: 
- Recall@10 had improved from 2% to 4% -- though this was partly because during testing, the model could only choose from the test-set vectors. 
- Cosine similarity improved marginally from 0.86 to 0.87. 
- Genre and Mirex predictions also worked incredibly well -- at around 99% and 96% top-1 retrieved category match. It is unclear why they have performed so well, but my educated guess for this is that these terms are descriptive, and the boundaries between categories are clearly delineated, making it easy for the model to make clear predictions. --> Perhaps this is also why the numeric columns linked to vibes aren't performing very well, because the semantic meaning between the 10 options per column bleed into each other? 

There are a few areas that require attention: 
- As mentioned, the statistics for numeric columns fare poorly. They generally are well-centered (their biases from true_value are in the order of 10^-2 to 10^-3), but their RMSE is in the order of 10^-1, suggesting that their errors lie on both the positive and negative sides of the true value. 
--- Learning from genre and mirex predictons, a hypothesis would be that in order for performance to improve, there needs to be a substantive and clear literary difference between the different options, to allow the model to "choose" the correct category and thereby limit its error. 
--- The bootstrapping strategy actually approximates the regression problem as a classification one -- the adjectives actually belong to 1 of 10 classes, and these 10 classes are ordered. So it actually makes sense that instead of having an regression objective function for these numeric columns, they should also have a classification objective function (like cross-entropy loss). 
--- This is also reflected in the manual_top_1_song_description_comparison.csv, where the numeric columns had a poor score that dragged the overall score down. 
- The statistics for gender surprisingly did not fare well. This is despite clear descriptions: "Performance gender: {gender}". 
--- Returning back to the original phrasing of "Sung by a {gender} vocalist" may work -- in experiment 1, that lead to a RMSE of 0.14ish instead of the current 0.5. Placement near the start of the sentence, and decoupling it from vocal presence may also help. 

## Improvements for Experiment 4 

### Embedding Cache
I don't have a reason why this wasn't done earlier, especially when it seems so obvious in hindsight -- it takes up around 2.5 hours to do the embeddings, which is easily 80-90% of compute runtime right now. 

The code should now push the train and test embeddings (.npy files) directly to the GCS bucket, and subsequent runs should call these .npy files directly from the bucket instead of having to re-compute them. 

### Recalibration of numeric columns bootstrapping
For each numeric column, instead of having 10 overlapping "classes" per column, we will now have 5 non-overlapping "classes" per column, the bounds being [0.0-0.20), [0.20-0.40), [0.40-0.60), [0.60-0.80), [0.80-1.00]. Reconfigure the list of adjectives that belong to each group. There should be 2 adjectives per group (the model should be able to adapt to some semantic variance instead of acting like a lookup-table). The idea is that each of these classes should be quite distinct from each other, to allow for separability. 

Right now, these classes are nominal, and do not account for the fact that they are ordered. This would be addressed in future iterations through means such as CORAL and ordinal loss (instead of the current cross-entropy loss). 

Remove the 'year' feature from all vectors (training, test, ground-truth, prediction). Also remove it from the input text in all descriptions.

## Vector Representation 
Each numeric feature will now be one-hot encoded, just like the categorical functions. That means that the vector will no longer be 29D. The model would return softmax probabilities over each of the classes -- e.g for the "happy" feature, it may produce a result of [0.1, 0.1, 0.6, 0.1, 0.1]. For the ground truth vector, if it was initially happy = 0.54, which belongs in the third class, the ground truth target vector might be represented as [0, 0, 1, 0, 0] for that column. 

That means that the current single 11-value numeric head should become 11 independent five-way softmax heads. It should not be a 55-way softmax. 

Point out the necessary changes to the neural network's output layer, since the vector is no longer in 29D. 

### Objective Function 
The objective function needs to change correspondingly. Instead of optimising for RMSE for these numeric columns, they will all be subjected to cross-entropy loss, just like the categorical functions. 

For now, assume every numeric feature head is weighted evenly. A 5-bin feature should not receive more emphasis than a 2-bin feature. L = l_numeric_1 + l_numeric2 + ... + l_numeric_n + l_categorical_1 + l_categorical_2 + ... + l_categorical_m

### Top 1 Comparison
In manual_top_1_song_description_comparison.csv, for every feature, we currently report whether it's in the correct or adjacent bins. Keep this metric. I want to introduce a new metric "exact-bin", to only mark it as correct if it predicts the correct bin exactly. This means that if the ground truth is [0, 0, 1, 0, 0] and the model predicts [0, 1, 0, 0, 0], then it would be wrong. 

### Other Notes
Do not implement validation and hyperparameter tuning yet. 