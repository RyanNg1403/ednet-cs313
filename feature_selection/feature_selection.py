import os
import json
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import lightgbm as lgb
from sklearn.model_selection import GroupShuffleSplit
from sklearn.feature_selection import f_classif, chi2

# ==========================================
# CONFIGURATION & SETUP
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Define absolute paths 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
INPUT_FILE = os.path.join(ROOT_DIR, "processed", "kt4_features.parquet")

OUTPUT_FS_DIR = os.path.join(ROOT_DIR, "output", "feature_selection")
OUTPUT_PLOTS_DIR = os.path.join(OUTPUT_FS_DIR, "plots")
OUTPUT_METRICS_DIR = os.path.join(OUTPUT_FS_DIR, "metrics")

def ensure_directories():
    """Ensure all required output directories exist."""
    for d in [OUTPUT_FS_DIR, OUTPUT_PLOTS_DIR, OUTPUT_METRICS_DIR]:
        os.makedirs(d, exist_ok=True)

def main():
    logger.info("=== STARTING FEATURE SELECTION PIPELINE ===")
    ensure_directories()
    
    # LOAD DATA----------------------------------------------------------------------
    logger.info(f"Loading data from {INPUT_FILE}...")
    try:
        df = pd.read_parquet(INPUT_FILE)
        logger.info(f"Data loaded successfully. Shape: {df.shape}")
    except FileNotFoundError:
        logger.error(f"Input file not found at {INPUT_FILE}. Please run feature engineering first.")
        return

    # TRAIN/TEST SPLIT (Grouped by User)
    logger.info("Splitting data into Train/Test (80/20) with GroupShuffleSplit...")
    # Using GroupShuffleSplit to prevent data leakage across users
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(gss.split(df, groups=df['user_id']))

    train_df = df.iloc[train_idx].copy()
    test_df = df.iloc[test_idx].copy()

    logger.info(f"Train Set: {len(train_df):,} rows ({train_df['user_id'].nunique():,} users)")
    logger.info(f"Test Set : {len(test_df):,} rows ({test_df['user_id'].nunique():,} users)")

    # Export Test Users List to CSV
    test_users_path = os.path.join(OUTPUT_FS_DIR, "test_users_list.csv")
    pd.Series(test_df['user_id'].unique(), name="test_user_id").to_csv(test_users_path, index=False)
    logger.info(f"Exported Test User IDs to {test_users_path}")

    #  MULTICOLLINEARITY ANALYSIS (PEARSON)---------------------------------------
    logger.info("Calculating Pearson Correlation Matrix...")
    feature_cols = [c for c in train_df.columns if c.startswith("feat_")]
    continuous_feats = [c for c in feature_cols if c != "feat_is_rapid_guess"]

    corr_matrix = train_df[continuous_feats].corr(method='pearson')

    # Export Correlation Matrix to CSV 
    corr_csv_path = os.path.join(OUTPUT_METRICS_DIR, "correlation_matrix.csv")
    corr_matrix.to_csv(corr_csv_path)
    logger.info(f"Exported Correlation Matrix CSV to {corr_csv_path}")

    # Plot & Save Heatmap
    plt.figure(figsize=(12, 10))
    sns.heatmap(corr_matrix, annot=True, fmt=".2f", cmap="RdBu_r",
                center=0, vmin=-1, vmax=1, square=True, linewidths=.5, cbar_kws={"shrink": .8})
    plt.title("Pearson Correlation Matrix (Continuous Features - Train Set)", fontsize=16, pad=20, fontweight='bold')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    corr_plot_path = os.path.join(OUTPUT_PLOTS_DIR, "01_correlation_matrix.png")
    plt.savefig(corr_plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved Correlation Matrix plot to {corr_plot_path}")

    #FILTER METHODS (ANOVA & CHI-SQUARE)---------------------------------------
    logger.info("Running Statistical Tests (ANOVA F-test & Chi-Square)...")
    y_train = train_df['target_is_correct']
    
    # Calculate scores
    f_scores, f_pvalues = f_classif(train_df[continuous_feats], y_train)
    chi_scores, chi_pvalues = chi2(train_df[['feat_is_rapid_guess']], y_train)
    
    # Create DataFrames, combine and export to CSV 
    anova_df = pd.DataFrame({
        'Feature': continuous_feats,
        'Method': 'ANOVA (F-test)',
        'Score': f_scores,
        'p-value': f_pvalues
    })
    
    chi_df = pd.DataFrame({
        'Feature': ['feat_is_rapid_guess'],
        'Method': 'Chi-Square',
        'Score': chi_scores,
        'p-value': chi_pvalues
    })
    
    stats_df = pd.concat([anova_df, chi_df], ignore_index=True)
    stats_df = stats_df.sort_values(by='Score', ascending=False).reset_index(drop=True)
    
    stats_csv_path = os.path.join(OUTPUT_METRICS_DIR, "statistical_tests_results.csv")
    stats_df.to_csv(stats_csv_path, index=False)
    logger.info(f"Exported Statistical Tests Results CSV to {stats_csv_path}")
    logger.info("Statistical testing completed.")

    #EMBEDDED METHOD (LIGHTGBM IMPORTANCE)----------------------------------------
    logger.info("Training LightGBM to extract Information Gain...")
    lgb_model = lgb.LGBMClassifier(
        n_estimators=100,
        max_depth=7,
        learning_rate=0.1,
        importance_type='gain',
        random_state=42,
        n_jobs=-1
    )
    lgb_model.fit(train_df[feature_cols], y_train)

    importance_df = pd.DataFrame({
        'Feature': feature_cols,
        'Gain': lgb_model.feature_importances_
    })
    total_gain = importance_df['Gain'].sum()
    importance_df['Contribution_Pct'] = (importance_df['Gain'] / total_gain * 100)
    importance_df = importance_df.sort_values(by='Gain', ascending=False).reset_index(drop=True)

    # Export LightGBM Importance to CSV
    lgb_csv_path = os.path.join(OUTPUT_METRICS_DIR, "lightgbm_importance.csv")
    importance_df.to_csv(lgb_csv_path, index=False)
    logger.info(f"Exported LightGBM Importance CSV to {lgb_csv_path}")

    # Plot & Save LightGBM Importance
    plt.figure(figsize=(10, 6))
    sns.barplot(x='Contribution_Pct', y='Feature', data=importance_df, hue='Feature', palette='viridis', legend=False)
    plt.title('LightGBM Feature Importance (Information Gain)', fontsize=14, pad=15, fontweight='bold')
    plt.xlabel('Contribution (%)', fontsize=12)
    plt.ylabel('Feature', fontsize=12)
    plt.tight_layout()
    
    lgb_plot_path = os.path.join(OUTPUT_PLOTS_DIR, "02_lightgbm_importance.png")
    plt.savefig(lgb_plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved LightGBM Importance plot to {lgb_plot_path}")

    #FINAL SELECTION & EXPORT-------------------------------------------------------
    logger.info("Exporting final selected features configuration...")
    
    final_features = [
        "feat_question_difficulty",
        "feat_reading_accuracy",
        "feat_listening_accuracy",
        "feat_answer_changes",
        "feat_total_attempts",
        "feat_is_rapid_guess",
        "feat_log_session_fatigue"
    ]

    # Lưu file config vào output_fs_dir để push lên git
    config_path = os.path.join(OUTPUT_FS_DIR, "selected_features.json")
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(final_features, f, indent=4)
        
    logger.info(f"Exported {len(final_features)} selected features to {config_path}")
    

if __name__ == "__main__":
    main()