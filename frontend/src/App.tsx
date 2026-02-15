import { useState } from 'react';
import axios from 'axios';

// Type Definitions
interface JournalEntry {
  company_code: string;
  posting_date: string;
  gl_account: string;
  amount_credit: number;
  item_text: string;
}

const API_BASE = "http://127.0.0.1:8000/api";

function App() {
  const [bankFile, setBankFile] = useState<File | null>(null);
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  
  // New State for AI Toggle
  const [useAI, setUseAI] = useState(false);

  const processFiles = async () => {
    if (!bankFile || !pdfFile) {
      alert("Please select both files.");
      return;
    }

    setLoading(true);
    setStatus("Uploading Bank Statement...");

    try {
      // 1. Upload Bank
      const bankData = new FormData();
      bankData.append("file", bankFile);
      await axios.post(`${API_BASE}/upload/bank`, bankData);

      setStatus(useAI ? "Analyzing PDF with GPT-4o (This takes a moment)..." : "Parsing Remittance Advice...");
      
      // 2. Upload PDF (With AI Flag)
      const pdfData = new FormData();
      pdfData.append("file", pdfFile);
      // Pass the toggle state to the backend
      await axios.post(`${API_BASE}/upload/remittance?use_ai=${useAI}`, pdfData);

      setStatus("Running Reconciliation Engine...");

      // 3. Reconcile
      const response = await axios.post(`${API_BASE}/reconcile`);
      setEntries(response.data);
      setStatus("Done!");

    } catch (error: any) {
      console.error(error);
      setStatus(`Error: ${error.response?.data?.detail || error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 p-10 font-sans text-gray-800">
      <div className="max-w-5xl mx-auto">
        <header className="mb-10 text-center">
          <h1 className="text-4xl font-bold text-slate-900 mb-2">Transformance</h1>
          <p className="text-slate-500 text-lg">Intelligent Cash Application Engine</p>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
          {/* Input Card */}
          <div className="md:col-span-1 bg-white p-6 rounded-xl shadow-sm border border-gray-200 h-fit">
            <h2 className="font-semibold text-lg mb-4 text-slate-700">1. Data Input</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-600 mb-1">Bank Statement</label>
                <input 
                  type="file" 
                  accept=".csv,.xlsx"
                  onChange={(e) => setBankFile(e.target.files?.[0] || null)}
                  className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-600 mb-1">Remittance (PDF)</label>
                <input 
                  type="file" 
                  accept=".pdf"
                  onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
                  className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                />
              </div>

              {/* AI Parser Toggle */}
              <div className="flex items-center bg-indigo-50 p-3 rounded-lg border border-indigo-100 mt-4">
                <input
                  type="checkbox"
                  id="ai-toggle"
                  checked={useAI}
                  onChange={(e) => setUseAI(e.target.checked)}
                  className="w-4 h-4 text-indigo-600 rounded focus:ring-indigo-500 cursor-pointer"
                />
                <label htmlFor="ai-toggle" className="ml-2 text-sm font-medium text-indigo-900 cursor-pointer select-none">
                  Enable AI Parsing (GPT-4o) 
                  <span className="ml-1 text-[10px] bg-indigo-200 text-indigo-800 px-1.5 py-0.5 rounded-full uppercase font-bold tracking-wide">Beta</span>
                </label>
              </div>

              <button 
                onClick={processFiles} 
                disabled={loading}
                className={`w-full mt-2 font-medium py-2.5 rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed ${
                  useAI 
                    ? "bg-indigo-600 hover:bg-indigo-700 text-white shadow-md shadow-indigo-200" 
                    : "bg-slate-900 hover:bg-slate-800 text-white"
                }`}
              >
                {loading ? "Processing..." : useAI ? "Run Intelligent Engine" : "Run Standard Engine"}
              </button>
              
              {status && <p className="text-xs text-center text-slate-500 mt-2 animate-pulse">{status}</p>}
            </div>
          </div>

          {/* Output Card */}
          <div className="md:col-span-2 bg-white p-6 rounded-xl shadow-sm border border-gray-200">
            <div className="flex justify-between items-center mb-4">
              <h2 className="font-semibold text-lg text-slate-700">2. Journal Entries</h2>
              {entries.length > 0 && (
                 <span className="bg-green-100 text-green-700 text-xs px-2 py-1 rounded-full font-medium">
                   {entries.length} Generated
                 </span>
              )}
            </div>

            {entries.length === 0 ? (
              <div className="h-64 flex flex-col items-center justify-center text-slate-400 border-2 border-dashed border-slate-100 rounded-lg">
                <p>No data generated yet.</p>
                <p className="text-sm">Upload files to begin reconciliation.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-slate-500 uppercase bg-slate-50">
                    <tr>
                      <th className="px-4 py-3">Post Date</th>
                      <th className="px-4 py-3">Account</th>
                      <th className="px-4 py-3 text-right">Credit (€)</th>
                      <th className="px-4 py-3">Text</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {entries.map((row, idx) => (
                      <tr key={idx} className="hover:bg-slate-50 transition-colors">
                        <td className="px-4 py-3 font-medium text-slate-900">{row.posting_date}</td>
                        <td className="px-4 py-3 font-mono text-slate-500">{row.gl_account}</td>
                        <td className="px-4 py-3 text-right font-medium text-emerald-600">
                          {row.amount_credit.toLocaleString('de-DE', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-4 py-3 text-slate-600">{row.item_text}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;