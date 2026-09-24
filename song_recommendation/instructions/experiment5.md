# Experiment 5

## Experiment 4 Review 
2 main trends: 
1) There was a large shift in the underlying geometry, because of the discretisation of the numeric columns. Many songs now had identical vectors, making exact song recommendation genuinely difficult because the songs were similar in this representation space. This is particularly evidenced by how the "answer-key" test top 1 accuracy dropped from a near-perfect score to 76.3%. 
2) In spite of the overlaps that resulted from the shift in geometry, there was a genuine improvement in Recall@10 from 0.04 to 0.12, indicating a substantive increase in the recommender's ability to return songs when their descriptions are passed through it. 

The main improvement beyond "bug-fixes" for this experiment would be in introducing ordinal encoding -- the problem being that the model currently doesn't recognise that within each numerical feature, the 5 softmax classes are not independent of each other but have an internal ordering. Therefore it weights all deviations equally, when in reality, a deviation between 0 and 0.8 should be punished more heavily than a deviation between 0.5 and 0.8. This could explain RMSE severely underperforms relative to MAE, because the model is unaware that some answers are more wrong than others here. 

## Experiment 5 Implementation 

### Increasing number of bins
Instead of 5 bins per numeric feature, these will now be changed to 8 non-overlapping bins. The bin widths would be: [0, 0.125), [0.125, 0.250), [0.250, 0.375), [0.375, 0.500), [0.500, 0.625), [0.625, 0.750), [0.750, 0.875), [0.875, 1.00]. 

Because these bins are non-overlapping, the descriptors should be as distinct from each other as possible from bin to bin. For instance, if the metric is "happy", it should be clear that between [0.375, 0.500] and [0.500, 0.625], one should be mildly unhappy and one should be mildly happy. 

### Cumulative Ordinal Encoding -- Coral 
Instead of using softmax predictions for each numerical feature head, these should now follow standard Coral implementation for Cumulative Ordinal Encoding. If the numeric feature has 8 bins, I should expect to see 7 threshold values per numerical feature head. 

These numerical heads should no longer be trained on cross-entropy loss. Instead, they should now be trained on ordinal cross-entropy loss. 

Develop these heads in-repository instead of relying on the `coral-ordinal` package. 

Therefore the loss function should now be modified accordingly. L = ordinal_loss(numeric_1) + ordinal_loss(numeric_2) + ... + cross_entropy(categorical_1) + cross_entropy(categorical_2) + ... Every feature head should be weighted evenly in the loss function, regardless of its type or the number of categories that it has. 

To be clear, ordinal_loss(dance) = mean BCE across 7 CORAL thresholds, not sum BCE across 7 coral thresholds. 

The output dimension for the neural network, I believe, should already be accounted for automatically. 

### Other Representations to generate other metrics
**Retrieval**
The representation described above is most useful for model training. 

After training is completed, convert the representation of bins from P(X > x) to P(X = x) (same as the Experiment 4 softmax implementation). Retrieval would be done in this "softmax" state (105D). To be clear, these class probabilities are not produced by a softmax layer, but are converted from CORAL's cumulative probabilities, and sum to 1. If there are n cumulative probabilities for CORAL, there should be n+1 class probabilities in this representation. 

Calculate all metrics except for the ones associated with numeric variables: MAE, RMSE, pearson correlation, R^2, bias_predicted_minus_true. In particular for top-1-comparison, for numeric features, there should be calculations for exact-bin-hit and adjacent-bin-hit, where adjacent-bin-hit describes for a feature whether the top-1-song has the same bin as the true-song OR is ian adjacent bin. 

**Numeric Evaluation**
For the metrics associated with numeric variables mentioned earlier (MAE, RMSE, oracle quantization error, pearson correlation, R^2, bias_predicte_minus_true), these numeric variables' class probabilities will be represented by a single number: a sum of P(X = k) * center[k], i.e the expected value of the bin. This representation is 28D (year is excluded here) -- the code should be able to derive this representation from the "softmax" representation (105D). 

The exact 8 bin centers are: [0.0625, 0.1875, 0.3125, 0.4375, 0.5625, 0.6875, 0.8125, 0.9375]. 

Also calculate the cosine similarity in this space. Note that this is different from retrieval-space-cosine-similarity. 

### Other Notes 
Ensure that the GCS embedding cache only contains updated train/test SentenceTransformer embeddings -- for this experiment, it should not change, the cache should be called. 

Again, we will not perform validation and hyperparameter tuning in this iteration. We will only begin after we confirm the architecture of the recommender. 