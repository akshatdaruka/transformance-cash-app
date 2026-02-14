import sys
import os
# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
import pandas as pd
import tempfile
import io
from src.ingestion import load_bank_statement
from src.parsers.bike_team import BikeTeamParser
from src.matcher import ReconciliationEngine

st.set_page_config(page_title="Transformance Cash App", page_icon="💶", layout="wide")

def save_uploaded_file(uploaded_file):
    try:
        uploaded_file.seek(0)
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{uploaded_file.name}") as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name
        return tmp_path
    except Exception as e:
        st.error(f"Error saving file: {e}")
        return None

def main():
    st.title("💶 Transformance | Cash Application Engine")
    st.markdown("**Senior Engineer Case Study:** Automated reconciliation of Bank Statements vs Remittance Advice.")

    with st.sidebar:
        st.header("Input Data")
        uploaded_bank = st.file_uploader("Bank Statement (CSV/Excel)", type=['csv', 'xlsx'])
        uploaded_pdf = st.file_uploader("Remittance Advice (PDF)", type=['pdf'])

    if uploaded_bank and uploaded_pdf:
        bank_path = save_uploaded_file(uploaded_bank)
        pdf_path = save_uploaded_file(uploaded_pdf)

        try:
            transactions = load_bank_statement(bank_path)
            
            parser = BikeTeamParser()
            if not parser.can_parse(pdf_path):
                st.error("❌ PDF format not recognized (Bike Team Parser failed).")
                st.stop()
            
            remittance = parser.parse(pdf_path)
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🏦 Bank Data")
                st.metric("Transactions", len(transactions))
                st.dataframe(pd.DataFrame([t.model_dump() for t in transactions]))
            
            with col2:
                st.subheader("📄 Remittance Data")
                st.metric("Total Declared", f"€{remittance.total_amount:,.2f}")
                st.dataframe(pd.DataFrame([l.model_dump() for l in remittance.lines]))

            st.divider()
            if st.button("Run Reconciliation", type="primary"):
                engine = ReconciliationEngine(transactions, [remittance])
                entries = engine.match_and_generate()
                
                if entries:
                    st.success(f"✅ Generated {len(entries)} GL Entries")
                    
                    result_df = pd.DataFrame([e.model_dump() for e in entries])
                    
                    # FORCE US Date Format for Excel (M/D/YYYY) as strings
                    # '2/3/2014' format
                    result_df['posting_date'] = pd.to_datetime(result_df['posting_date']).dt.strftime('%-m/%-d/%Y')
                    result_df['document_date'] = pd.to_datetime(result_df['document_date']).dt.strftime('%-m/%-d/%Y')

                    export_df = result_df.rename(columns={
                        "company_code": "Company Code", "posting_date": "Posting Date",
                        "document_date": "Document Date", "document_type": "Document Type",
                        "gl_account": "GL Account", "amount_credit": "Credit",
                        "currency": "Currency", "item_text": "Item Text"
                    })
                    export_df["Line Number"] = range(1, len(export_df) + 1)
                    export_df["Debit"] = ""
                    
                    cols = ["Company Code", "Posting Date", "Document Date", "Document Type", 
                            "Line Number", "GL Account", "Debit", "Credit", "Currency", "Item Text"]
                    final_df = export_df[cols]

                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        final_df.to_excel(writer, index=False)
                    
                    st.download_button(
                        label="📥 Download Journal Entries (.xlsx)",
                        data=output.getvalue(),
                        file_name="Final_Journal_Entries.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.warning("⚠️ No matches found. Check amount exactness.")
        except Exception as e:
            st.error(f"Processing Error: {e}")
    else:
        st.info("👈 Please upload both files to begin.")

if __name__ == "__main__":
    main()