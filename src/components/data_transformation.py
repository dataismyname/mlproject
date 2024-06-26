import sys
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import skew
from scipy.stats.mstats import winsorize
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler

from src.exception import CustomException
from src.logger import logging
from src.utils import save_object

@dataclass
class DataTransformationConfig:
    preprocessor_obj_file_path: str = os.path.join('artifacts', 'preprocessor.pkl')
    label_encoder_file_path: str = os.path.join('artifacts', 'label_encoder.pkl')
    feature_names_file_path: str = os.path.join('artifacts', 'feature_names.pkl')
    correlated_features_file_path: str = os.path.join('artifacts', 'target_corr_features.pkl')

class DataTransformation:
    def __init__(self):
        self.data_transformation_config = DataTransformationConfig()

    def get_data_transformation_obj(self, features):
        """
        This function is responsible of data transformation
        """
        try:

            #Defining numerical and categorical columns
            # Select numerical columns
            num_columns = features.select_dtypes(include='number').columns.tolist()
            
            # Select categorical columns, excluding the target column
            cat_columns = features.select_dtypes(exclude='number').columns.tolist()
            cat_columns = [col for col in cat_columns if col != 'Attrition_Flag'] 

            #Pipelines and Column Transformer
            num_pipeline = Pipeline(steps=[("scaler", StandardScaler())])
            cat_pipeline = Pipeline(steps=[("ohe", OneHotEncoder()),])

            logging.info(f"Numerical columns: {num_columns}")
            logging.info(f"Categorical columns: {cat_columns}")
            
            preprocessor=ColumnTransformer(
                [
                    ("num_pipeline", num_pipeline, num_columns),
                    ("cat_pipeline", cat_pipeline, cat_columns),
                ])

            return preprocessor
        
        except Exception as e:
            raise CustomException(e,sys)

    def initiate_data_transformation(self,train_path,test_path):
        """
        This function is responsable of data initial transformation
        """

        try:
            train_df=pd.read_csv(train_path)
            test_df=pd.read_csv(test_path)

            logging.info("Read train and test data completed.")

            #Dropping unnecessary columns 
            logging.info("Preparing DataFrame")
            train_df = train_df.iloc[:,1:-2]
            test_df = test_df.iloc[:,1:-2]

            # Handling outliers
            for df in [train_df, test_df]:
                for col in df.select_dtypes(include='number').columns:
                    skewness = skew(df[col])
                    limits = (0.05, 0.25) if skewness > 1 else (0.25, 0.05) if skewness < -1 else (0.15, 0.15)
                    df[col] = winsorize(df[col], limits=limits)
            
            # Creating new features
            for df in [train_df, test_df]:
                df['Products_year'] = df['Total_Relationship_Count'] / df['Months_on_book'] * 12
                #df['Transaction_Amt_Change_Rate'] = (df['Total_Trans_Amt'] - df['Total_Trans_Amt'].shift(1)) / df['Total_Trans_Amt'].shift(1)
                #df['Transaction_Ct_Change_Rate'] = (df['Total_Trans_Ct'] - df['Total_Trans_Ct'].shift(1)) / df['Total_Trans_Ct'].shift(1)

            #Defining features and target columns
            target_column = 'Attrition_Flag'
            train_features = train_df.drop(columns=[target_column], axis = 1)
            test_features = test_df.drop(columns=[target_column], axis = 1)
            
            # Preprocessing object initialized
            logging.info("Obtaining preprocessing object.")
            preprocessing_obj=self.get_data_transformation_obj(train_features)
            
            logging.info(f"Applying preprocessing object on training dataframe and testing dataframe.")
            train_features_transformed = preprocessing_obj.fit_transform(train_features)
            test_features_transformed = preprocessing_obj.transform(test_features)

            logging.info(f"Saving preprocessing object.")

            save_object(
                file_path=self.data_transformation_config.preprocessor_obj_file_path,
                obj=preprocessing_obj
            )
            
            #Saving encoded features column names
            enc_feat_col = pd.get_dummies(train_features).columns
            save_object(file_path=self.data_transformation_config.feature_names_file_path, obj=enc_feat_col)
            # Apply preprocessing and encode target
            le = LabelEncoder()
            train_target_encoded = le.fit_transform(train_df[target_column])
            test_target_encoded = le.transform(test_df[target_column])

            # Serialize label encoder
            save_object(self.data_transformation_config.label_encoder_file_path, obj = le)

            # Transformed and encoded DataFrames
            train_df_trans = pd.DataFrame(train_features_transformed, columns=enc_feat_col)
            train_df_trans[target_column] = train_target_encoded
            train_df_trans.dropna(inplace=True)

            test_df_trans = pd.DataFrame(test_features_transformed, columns=enc_feat_col)
            test_df_trans[target_column] = test_target_encoded
            test_df_trans.dropna(inplace=True)

            # Calculate correlation matrix and select correlated features
            corrmat = train_df_trans.corr()
            target_corr_bool = corrmat.loc[target_column,:].between(0.1, 0.65) | corrmat.loc[target_column,:].between(-0.65, -0.1)
            correlated_features = corrmat.columns[target_corr_bool].tolist()

            # Serialize the correlated features
            save_object(self.data_transformation_config.correlated_features_file_path, obj=correlated_features)

            # Filter data based on selected features
            train_arr = train_df_trans[correlated_features + [target_column]].values
            test_arr = test_df_trans[correlated_features + [target_column]].values

            return train_arr, test_arr
        except Exception as e:
            raise CustomException(e, sys)