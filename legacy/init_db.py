import pandas as pd
import sqlite3
import os

# 1. Update this to your actual file name
csv_file = 'Retail_IQ_Sales_Cleaned.xlsx - Sheet1.csv'

if os.path.exists(csv_file):
    df = pd.read_csv(csv_file)
    
    # --- CRITICAL FIX: Standardize Column Names for SQL ---
    # Converts "Item Type" -> "item_type", "Sales" -> "sales", etc.
    df.columns = [col.lower().replace(' ', '_') for col in df.columns]
    
    # 2. Connect to the database
    conn = sqlite3.connect('retailiq.db')
    
    # 3. Save the data
    df.to_sql('sales_data', conn, if_exists='replace', index=False)
    conn.close()
    print("✅ Success! 'retailiq.db' created with clean column names.")
else:
    print(f"❌ Error: Could not find {csv_file} in the python folder.")