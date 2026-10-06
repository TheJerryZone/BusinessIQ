import pandas as pd
import sqlite3
import os

# 1. Define Paths
excel_path = r"C:\Users\91636\Documents\Real-Time Sales Analytics Dashboard\data\Retail_IQ_Sales_Cleaned.xlsx"
db_folder = r"C:\Users\91636\Documents\Real-Time Sales Analytics Dashboard\database"
db_path = os.path.join(db_folder, "retailiq.db")

# 2. Create the database folder if it doesn't exist
if not os.path.exists(db_folder):
    os.makedirs(db_folder)
    print(f"Created folder: {db_folder}")

# 3. Process Data
if os.path.exists(excel_path):
    print("Reading Excel file...")
    # Read the Excel file
    df = pd.read_excel(excel_path)
    
    # FIX: Standardize column names (lowercase and underscores)
    # This fixes the 'item_type' and 'sales' errors in your notebooks
    df.columns = [col.lower().replace(' ', '_') for col in df.columns]
    
    # 4. Save to SQLite
    conn = sqlite3.connect(db_path)
    df.to_sql('sales_data', conn, if_exists='replace', index=False)
    conn.close()
    
    print(f"✅ Success! Database created at: {db_path}")
    print("✅ Columns standardized: 'item_type', 'sales', etc. are now ready.")
else:
    print(f"❌ Error: Could not find the Excel file at {excel_path}")