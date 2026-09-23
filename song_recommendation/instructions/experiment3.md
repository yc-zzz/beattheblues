# Experiment 3 Instructions 

## Audit of Experiment 2 
Relative to experiment 1, performance deteriorated on many counts: 
- RMSE did not decline for most numeric functions 
- MIREX error increased, suggesting that randomly sampling from the pool of MIREX descriptions increased ambiguity about the song's character rather than giving it some identity, 
- Gender's error increased significantly, signifying that perhaps gender could be signified more explicitly. 

Other errors that were identified include: 
- Objective function may not be right -- cosine similarity cares only about pointing vectors in the right direction, but not the magnitude of these vectors. This also means that currently, the model is intensity-agnostic: A vector that is short and a vector that is long pointing in the same direction is considered similar, but one could be dramatically more sad, more aggressive than another song. 
- A lack of hyperparameter tuning, and relevant set-up to enable that -- no validation set, weight decay (AdamW), early stopping mechanisms. 

Finally, experiment set-up was noted to be incomplete. Vector quality can be audited, but not exact run reproductions. 

## New proposed changes: 

### Vector Representation
All categorical variables will no longer retain their ordinal form -- they will now all be one-hot encoded. This is because now the model will be trained to output probabilities for each option in a categorical variable. That means for a variable like Mirex, it would no longer output "3" corresponding to the third category being most likely, but it would output something like [0.05, 0.05, 0.80, 0.05, 0.05], representing the probability of belonging to a certain class/cluster. Correspondingly, a ground truth vector for mirex could represent something like [0, 0, 1, 0, 0]. 

For each prediction, the vector can be represented as [num_pred_1, num_pred_2... c1p1, c1p2, c2p1, c2p2, c3p3, ...], where num_pred refers to numerical predictions, and c_xp_y refers to the probability of belonging to a certain class y (e.g female) in column x (e.g gender). 

Vector representation remains unchanged at 29D.  

### Objective Function 
Instead of using cosine similarity as the training objective function, the model should be trained on a new combined function. 

For numeric columns, it should minimise mean-squared error (which also minimises RMSE). 

For categorical columns, a softmax head should be created for every categorical variable, cross-entropy losses should be calculated for all of these columns, and their average (l_categorical) should be minimised. These two losses would then be combined into a linear function with weights, i.e l = lambda_n * l_numeric + lambda_c * l_categorical, where lambda_n and lambda_c are the coefficients for numeric loss (RMSE) and categorical loss (cross-entropy). lambda_n and lambda_c should be tuned during hyperparameter tuning using the validation set. 

For this experiment, used fixed baseline weights lambda_n = 1 and lambda_c = 1. 

For retrieval, as explained earlier, concatenate calibrated numeric predictions and categorical probabilities. Assume numeric and categorical weights are equal (every feature is equally important in retrieval). Apply the same feature weighting to candidate vectors. Do not retrieve with raw logits (always use softmax outputs). 

### Train-Test Split 
Separate the train and test vectors, such that vectors in the train set do not appear in the candidate set during testing, i.e when a test set description is being passed to the model, the model should only be able to choose within the test-set vectors. This prevents the model from favouring/disfavouring vectors observed during training. 

The later section talks about the creation of the validation set. It should come directly from the training set. Ensure there is clear separation between train-validation-test splits. 

### Validation -- do not implement now 
<future>
Create a validation set by withholding 1/5 of the training set -- we will implement k-fold cross-validation in later experiments. The parameters to be tuned during hyperparameter optimisation are: lambda_c, weight decay parameter for AdamW. lambda_n will be set to 1 (as a normalising constant). Optuna should be used as the hyperparameter tuner, and the metric it should optimise would be validation Recall@10. Make sure to cache the SentenceTransformer embeddings to make sure that they are not re-computed per trial/fold. Run 15 trials, with early stopping where necessary. 

At every epoch, track training loss, validation loss. Every 5 epochs, track average cosine similarity between true vector and predicted vector, as well as Recall@10. Early stopping and selection of best epoch should also use Recall@10 as the objective. 

Plot charts for all these metrics as training progresses. Also include hyperparameter charts. 
</future>

### Feature Engineering 
Add the full mirex labels back into the song description instead of randomly sampling one descriptor from the pool of descriptions. Modify the language around these group of labels, e.g "The song belongs to this specific vibe cluster: {mirex}". 

### Manual Song Description Comparison 
Also, create a csv comparing the true vector with the top-1-vector. First list the true-song id and bootstrapped description, then that of the top-1-song. Then, compare by feature whether the top-1-song's description aligns with the true song. For each numeric column, it's considered correct if its descriptor is in the same group or groups adjacent to that of the true song. Assign a score of 1 if correct and 0 if not. 

For instance, if the true song description had "dance" an adjective like "unrhythmic" (within the [0.10, 0.25] range), it would be correct if it had an adjective corresponding to [0, 0.15], [0.10, 0.25], [0.20, 0.35], i.e adjectives belonging to its own group or adjacent groups. Therefore, ("still", "non-danceable"), ("unrhythmic", "reserved"), ("subtle", "light-footed") would all be considered acceptable answers if it was in the top-1-song. However, if it had a adjective like "still", then it would only be correct if it belonged to the [0, 0.15], [0.10, 0.25] categories, meaning that the correct answers would be ("still", "non-danceable"), ("unrhythmic", "reserved"). 

For categorical variables, it would be considered correct if there was an exact match. For instance, if the true-song description's gender column has "female", then the top-1-song description should have "female" as well. 

Sum up the scores for each column. 