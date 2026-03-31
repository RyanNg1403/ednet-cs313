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

# Đã cập nhật file data mới của team
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
INPUT_FILE = os.path.join(ROOT_DIR, "processed", "kt4_features_1.parquet") 

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
        logger.error(f"Input file not found at {INPUT_FILE}.")
        return

    # TRAIN/TEST SPLIT (Grouped by User)
    logger.info("Splitting data into Train/Test (80/20) with GroupShuffleSplit...")
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

    #Feature Categorization
    feature_cols = [c for c in train_df.columns if c.startswith("feat_")]
    # Tự động tìm các biến categorical (có 2 giá trị như 0/1, True/False)
    cat_feats = [c for c in feature_cols if train_df[c].nunique() <= 2]
    # Còn lại là continuous
    cont_feats = [c for c in feature_cols if c not in cat_feats]

    # MULTICOLLINEARITY ANALYSIS (PEARSON)---------------------------------------
    if cont_feats:
        logger.info("Calculating Pearson Correlation Matrix...")
        corr_matrix = train_df[cont_feats].corr(method='pearson')

        corr_csv_path = os.path.join(OUTPUT_METRICS_DIR, "correlation_matrix.csv")
        corr_matrix.to_csv(corr_csv_path)

        plt.figure(figsize=(14, 12))
        sns.heatmap(corr_matrix, annot=True, fmt=".2f", cmap="RdBu_r",
                    center=0, vmin=-1, vmax=1, square=True, linewidths=.5, cbar_kws={"shrink": .8})
        plt.title("Pearson Correlation Matrix (Continuous Features)", fontsize=16, pad=20, fontweight='bold')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        corr_plot_path = os.path.join(OUTPUT_PLOTS_DIR, "01_correlation_matrix.png")
        plt.savefig(corr_plot_path, dpi=150, bbox_inches='tight')
        plt.close()
        logger.info(f"Saved Correlation Matrix plot to {corr_plot_path}")

    # FILTER METHODS (ANOVA & CHI-SQUARE)---------------------------------------
    logger.info("Running Statistical Tests...")
    y_train = train_df['target_is_correct']
    stats_dfs = []

    if cont_feats:
        #Fill NaN with 0 to avoid errors in Scikit-learn
        X_cont = train_df[cont_feats].fillna(0)
        f_scores, f_pvalues = f_classif(X_cont, y_train)
        stats_dfs.append(pd.DataFrame({
            'Feature': cont_feats,
            'Method': 'ANOVA (F-test)',
            'Score': f_scores,
            'p-value': f_pvalues
        }))

    if cat_feats:
        #Fill NaN with 0 to avoid errors in Scikit-learn
        X_cat = train_df[cat_feats].fillna(0)
        chi_scores, chi_pvalues = chi2(X_cat, y_train)
        stats_dfs.append(pd.DataFrame({
            'Feature': cat_feats,
            'Method': 'Chi-Square',
            'Score': chi_scores,
            'p-value': chi_pvalues
        }))

    if stats_dfs:
        stats_df = pd.concat(stats_dfs, ignore_index=True)
        stats_df = stats_df.sort_values(by='Score', ascending=False).reset_index(drop=True)
        stats_csv_path = os.path.join(OUTPUT_METRICS_DIR, "statistical_tests_results.csv")
        stats_df.to_csv(stats_csv_path, index=False)
        logger.info(f"Exported Statistical Tests Results to {stats_csv_path}")

    # EMBEDDED METHOD (LIGHTGBM IMPORTANCE)----------------------------------------
    logger.info("Training LightGBM to extract Information Gain...")
    lgb_model = lgb.LGBMClassifier(
        n_estimators=100, max_depth=7, learning_rate=0.1,
        importance_type='gain', random_state=42, n_jobs=-1
    )
    lgb_model.fit(train_df[feature_cols], y_train)

    importance_df = pd.DataFrame({
        'Feature': feature_cols,
        'Gain': lgb_model.feature_importances_
    })
    total_gain = importance_df['Gain'].sum()
    importance_df['Contribution_Pct'] = (importance_df['Gain'] / total_gain * 100)
    importance_df = importance_df.sort_values(by='Gain', ascending=False).reset_index(drop=True)

    lgb_csv_path = os.path.join(OUTPUT_METRICS_DIR, "lightgbm_importance.csv")
    importance_df.to_csv(lgb_csv_path, index=False)

    plt.figure(figsize=(10, 8))
    sns.barplot(x='Contribution_Pct', y='Feature', data=importance_df, hue='Feature', palette='viridis', legend=False)
    plt.title('LightGBM Feature Importance (Information Gain)', fontsize=14, pad=15, fontweight='bold')
    plt.xlabel('Contribution (%)', fontsize=12)
    plt.ylabel('Feature', fontsize=12)
    plt.axvline(x=0.5, color='red', linestyle='--', linewidth=2, label='0.5% Cut-off Threshold')
    plt.legend(loc='lower right')
    plt.tight_layout()
    lgb_plot_path = os.path.join(OUTPUT_PLOTS_DIR, "02_lightgbm_importance.png")
    plt.savefig(lgb_plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info("Saved LightGBM Importance plot.")

if __name__ == "__main__":
    main()