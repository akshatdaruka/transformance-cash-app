import { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE = "http://localhost:8000/api";

export default function ConfigPanel() {
  const [bankConfigs, setBankConfigs] = useState<any[]>([]);
  const [vendorConfigs, setVendorConfigs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Fetch configs on load
  useEffect(() => {
    fetchConfigs();
  }, []);

  const fetchConfigs = async () => {
    try {
      const bankRes = await axios.get(`${API_BASE}/config/bank-layout`);
      const vendorRes = await axios.get(`${API_BASE}/config/vendor-rules`);
      setBankConfigs(bankRes.data);
      setVendorConfigs(vendorRes.data);
    } catch (err) {
      console.error("Failed to load configs", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* SECTION 1: BANK LAYOUTS */}
      <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
        <h2 className="text-xl font-bold text-slate-800 mb-4 flex items-center">
          🏦 Bank Statement Mappings
        </h2>
        <p className="text-sm text-slate-500 mb-4">
          Define which columns in your CSV correspond to system fields.
        </p>
        
        {loading ? <p>Loading...</p> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-slate-500 uppercase bg-slate-50">
                <tr>
                  <th className="px-4 py-3">Bank Name</th>
                  <th className="px-4 py-3">Date Col</th>
                  <th className="px-4 py-3">Amount Col</th>
                  <th className="px-4 py-3">Delimiter</th>
                  <th className="px-4 py-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {bankConfigs.map((conf) => (
                  <tr key={conf.id} className="border-b border-gray-100">
                    <td className="px-4 py-3 font-medium text-slate-900">{conf.name}</td>
                    <td className="px-4 py-3 font-mono text-blue-600">{conf.date_col}</td>
                    <td className="px-4 py-3 font-mono text-green-600">{conf.amount_col}</td>
                    <td className="px-4 py-3 bg-gray-50 text-center font-mono">"{conf.delimiter}"</td>
                    <td className="px-4 py-3">
                      <button className="text-indigo-600 hover:underline">Edit</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* SECTION 2: VENDOR AI RULES */}
      <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
        <h2 className="text-xl font-bold text-slate-800 mb-4 flex items-center">
          🤖 Vendor AI Rules
        </h2>
        <p className="text-sm text-slate-500 mb-4">
          "Prompt Injection" settings. These keywords guide the AI for specific vendors.
        </p>

        {loading ? <p>Loading...</p> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-slate-500 uppercase bg-slate-50">
                <tr>
                  <th className="px-4 py-3">Vendor Name</th>
                  <th className="px-4 py-3">Total Label (Keyword)</th>
                  <th className="px-4 py-3">Table Start (Keyword)</th>
                  <th className="px-4 py-3">Auto-Detect</th>
                </tr>
              </thead>
              <tbody>
                {vendorConfigs.map((conf) => (
                  <tr key={conf.id} className="border-b border-gray-100">
                    <td className="px-4 py-3 font-medium text-slate-900">{conf.name}</td>
                    <td className="px-4 py-3">
                      <span className="bg-indigo-100 text-indigo-800 px-2 py-1 rounded text-xs font-mono">
                        "{conf.total_label}"
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-500">"{conf.table_start_keyword}"</td>
                    <td className="px-4 py-3 text-xs text-slate-400">
                      Contains "{conf.identifier_keyword}"
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}