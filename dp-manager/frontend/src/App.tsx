import React, { useMemo, useState, useEffect } from "react";

interface IOListItem {
  id: number;
  header_id: number;
  io_no: string | null;
  io_name: string | null;
  io_type: string | null;
  description: string | null;
  remarks: string | null;
  raw_data: string | null;  // 파일 구조 그대로 저장된 원본 데이터
  data_channel_id: string | null;
  is_duplicate_data_channel_id: boolean;
  is_duplicate_description: boolean;
  is_duplicate_mqtt_tag: boolean;
  has_missing_required: boolean;
  created_at: string;
  updated_at: string;
}

interface ItemStatistics {
  total: number;
  by_device: { [key: string]: number };
}

interface IOListHeader {
  id: number;
  uuid: string;
  hull_no: string;
  imo: string;
  date_key: string;
  file_name: string;
  created_at: string;
  updated_at: string;
  item_count: number;
}

interface Filters {
  hull_nos: string[];
  imos: string[];
  date_keys: string[];
}

export default function App() {
  const apiBase = useMemo(
    () => import.meta.env.VITE_API_BASE_URL || "http://localhost:18000",
    []
  );

  // 상태 관리
  const [headers, setHeaders] = useState<IOListHeader[]>([]);
  const [items, setItems] = useState<IOListItem[]>([]);
  const [filters, setFilters] = useState<Filters>({ hull_nos: [], imos: [], date_keys: [] });
  const [selectedHeader, setSelectedHeader] = useState<IOListHeader | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");

  // 필터 상태
  const [filterHullNo, setFilterHullNo] = useState<string>("");
  const [filterIMO, setFilterIMO] = useState<string>("");
  const [filterDateKey, setFilterDateKey] = useState<string>("");

  // 업로드 상태 (사용자 입력 제거)

  // 편집 상태
  const [editingItem, setEditingItem] = useState<IOListItem | null>(null);
  const [editingRawData, setEditingRawData] = useState<Record<string, any>>({});
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeviceModal, setShowDeviceModal] = useState(false);
  const [editingDevice, setEditingDevice] = useState<{id?: number, device_name: string, protocol: string} | null>(null);
  
  // 항목 필터 상태
  const [showDuplicates, setShowDuplicates] = useState<boolean>(false);
  const [showMissingRequired, setShowMissingRequired] = useState<boolean>(false);
  const [searchText, setSearchText] = useState<string>("");
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");
  const [devices, setDevices] = useState<Array<{id: number, device_name: string, protocol: string}>>([]);
  
  // 선택된 헤더 (체크박스)
  const [selectedHeaders, setSelectedHeaders] = useState<Set<number>>(new Set());
  const [lastSelectedIndex, setLastSelectedIndex] = useState<number | null>(null);
  
  // 창 크기 상태
  const [windowSize, setWindowSize] = useState({
    width: window.innerWidth,
    height: window.innerHeight
  });
  
  // 창 크기 변경 감지
  useEffect(() => {
    const handleResize = () => {
      setWindowSize({
        width: window.innerWidth,
        height: window.innerHeight
      });
    };
    
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // 필터 옵션 로드
  useEffect(() => {
    loadFilters();
  }, []);

  // 헤더 목록 로드
  useEffect(() => {
    loadHeaders();
  }, [filterHullNo, filterIMO, filterDateKey]);

  const loadFilters = async () => {
    try {
      const res = await fetch(`${apiBase}/iolist/filters`);
      if (res.ok) {
        const data = await res.json();
        setFilters(data);
      }
    } catch (e) {
      console.error("필터 로드 실패:", e);
    }
  };

  const loadHeaders = async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (filterHullNo) params.append("hull_no", filterHullNo);
      if (filterIMO) params.append("imo", filterIMO);
      if (filterDateKey) params.append("date_key", filterDateKey);

      const res = await fetch(`${apiBase}/iolist/headers?${params}`);
      if (!res.ok) {
        throw new Error(`조회 실패: ${res.status}`);
      }
      const data = await res.json();
      setHeaders(data);
    } catch (e: any) {
      setError(e.message || "헤더 목록 로드 실패");
    } finally {
      setLoading(false);
    }
  };

  const loadItems = async (headerId: number) => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (showDuplicates) params.append("show_duplicates", "true");
      if (showMissingRequired) params.append("show_missing_required", "true");
      
      const res = await fetch(`${apiBase}/iolist/headers/${headerId}/items?${params}`);
      if (!res.ok) {
        throw new Error(`항목 조회 실패: ${res.status}`);
      }
      const data = await res.json();
      setItems(data);
    } catch (e: any) {
      setError(e.message || "항목 목록 로드 실패");
    } finally {
      setLoading(false);
    }
  };
  
  // 필터 변경 시 항목 다시 로드
  useEffect(() => {
    if (selectedHeader) {
      loadItems(selectedHeader.id);
    }
  }, [showDuplicates, showMissingRequired]);

  // 파일명에서 Hull NO와 IMO NO 추출
  const parseFilename = (filename: string): { hullNo?: string; imo?: string } => {
    const match = filename.match(/H(\d+).*?IMO(\d+)/i);
    if (match) {
      return {
        hullNo: `H${match[1]}`,
        imo: `IMO${match[2]}`,
      };
    }
    return {};
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    if (!file) return;
    
    // 파일명에서 자동 추출
    const parsed = parseFilename(file.name);
    if (!parsed.hullNo || !parsed.imo) {
      setError("파일명에서 Hull Number와 IMO Number를 추출할 수 없습니다. (예: H2567_IMO9991862_IOList.xlsx)");
      e.target.value = ""; // 파일 입력 초기화
      return;
    }

    setLoading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const params = new URLSearchParams();
      params.append("hull_no", parsed.hullNo);
      params.append("imo", parsed.imo);

      const res = await fetch(`${apiBase}/upload/iolist?${params}`, {
        method: "POST",
        body: form,
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: "업로드 실패" }));
        throw new Error(errorData.detail || `업로드 실패: ${res.status}`);
      }

      // 업로드 성공 후 초기화 및 새로고침
      e.target.value = ""; // 파일 입력 초기화
      await loadHeaders();
      await loadFilters();
      alert("업로드가 완료되었습니다.");
    } catch (e: any) {
      setError(e.message || "업로드 실패");
    } finally {
      setLoading(false);
    }
  };

  const handleHeaderSelect = async (header: IOListHeader) => {
    setSelectedHeader(header);
    await loadItems(header.id);
    await loadDevices(header.id);
  };

  const loadDevices = async (headerId: number) => {
    try {
      const res = await fetch(`${apiBase}/iolist/headers/${headerId}/devices`);
      if (res.ok) {
        const data = await res.json();
        setDevices(data);
      }
    } catch (e) {
      console.error("Device 로드 실패:", e);
    }
  };

  const handleCreateClick = async () => {
    if (!selectedHeader) {
      setError("IOLIST를 먼저 선택해주세요.");
      return;
    }
    
    // 빈 raw_data 객체 생성 (MQTT 필수 컬럼들)
    const emptyRawData: Record<string, any> = {
      "Resource": "",
      "Data type": "",
      "RuleNaming": "hs4sd_v1",
      "Level 1": "",
      "Level 2": "",
      "Level 3": "",
      "Level 4": "",
      "Miscellaneous": "",
      "Measure": "",
      "Description": "",
      "Calculation": "",
      "MQTT Tag": "",
      "Remark": ""
    };
    
    setEditingItem(null);
    setEditingRawData(emptyRawData);
    await loadDevices(selectedHeader.id);
    setShowEditModal(true);
  };

  const handleEditClick = (item: IOListItem) => {
    try {
      const rawData = item.raw_data ? JSON.parse(item.raw_data) : {};
      // 기존 값이 있는 컬럼은 현재 입력된 값 유지 (모든 컬럼 포함)
      const allColumns = [
        "Resource", "Data type", "RuleNaming", "Level 1", "Level 2", "Level 3", "Level 4",
        "Miscellaneous", "Measure", "Description", "Calculation", "MQTT Tag", "Remark"
      ];
      const completeRawData: Record<string, any> = {};
      allColumns.forEach(col => {
        completeRawData[col] = rawData[col] || "";
      });
      
      setEditingItem(item);
      setEditingRawData(completeRawData);
      if (selectedHeader) {
        loadDevices(selectedHeader.id);
      }
      setShowEditModal(true);
    } catch (e) {
      setError("데이터 파싱 실패");
    }
  };

  const handleSaveItem = async () => {
    if (!selectedHeader) {
      setError("IOLIST를 먼저 선택해주세요.");
      return;
    }
    
    // 필수 값 검증
    const requiredFields = ["Resource", "Data type", "RuleNaming", "Level 1", "Measure"];
    const missingFields = requiredFields.filter(field => {
      const value = editingRawData[field];
      return !value || (typeof value === "string" && value.trim() === "");
    });
    
    if (missingFields.length > 0) {
      alert(`필수 항목을 입력해주세요: ${missingFields.join(", ")}`);
      return;
    }
    
    setLoading(true);
    setError("");
    try {
      // raw_data를 JSON 문자열로 변환
      const rawDataJson = JSON.stringify(editingRawData, null, 2);
      
      // 호환성을 위한 필드 추출
      const mqttTag = editingRawData["MQTT Tag"] || "";
      const description = editingRawData["Description"] || "";
      const dataType = editingRawData["Data type"] || "";
      const remark = editingRawData["Remark"] || "";
      
      let res;
      if (editingItem) {
        // 수정 모드
        res = await fetch(`${apiBase}/iolist/items/${editingItem.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            raw_data: rawDataJson,
            io_no: mqttTag,
            io_name: description || editingRawData["Measure"] || "",
            io_type: dataType,
            description: description,
            remarks: remark,
          }),
        });
      } else {
        // 생성 모드
        res = await fetch(`${apiBase}/iolist/headers/${selectedHeader.id}/items`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            raw_data: rawDataJson,
            io_no: mqttTag,
            io_name: description || editingRawData["Measure"] || "",
            io_type: dataType,
            description: description,
            remarks: remark,
          }),
        });
      }

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: editingItem ? "수정 실패" : "생성 실패" }));
        throw new Error(errorData.detail || (editingItem ? "수정 실패" : "생성 실패"));
      }

      setEditingItem(null);
      setEditingRawData({});
      setShowEditModal(false);
      await loadItems(selectedHeader.id);
      alert(editingItem ? "항목이 수정되었습니다." : "항목이 추가되었습니다.");
    } catch (e: any) {
      setError(e.message || (editingItem ? "항목 수정 실패" : "항목 생성 실패"));
    } finally {
      setLoading(false);
    }
  };

  // 검색 및 필터링된 항목
  const filteredAndSortedItems = useMemo(() => {
    let filtered = [...items];
    
    // 검색 필터
    if (searchText.trim()) {
      const searchLower = searchText.toLowerCase();
      filtered = filtered.filter(item => {
        try {
          const rawData = item.raw_data ? JSON.parse(item.raw_data) : {};
          const searchableText = [
            item.io_no || "",
            item.io_name || "",
            item.io_type || "",
            item.description || "",
            item.data_channel_id || "",
            JSON.stringify(rawData)
          ].join(" ").toLowerCase();
          return searchableText.includes(searchLower);
        } catch {
          return false;
        }
      });
    }
    
    // 정렬
    if (sortColumn) {
      filtered.sort((a, b) => {
        let aVal: any = "";
        let bVal: any = "";
        
        switch (sortColumn) {
          case "#":
            aVal = a.id || 0;
            bVal = b.id || 0;
            break;
          case "Device":
            try {
              const aRaw = a.raw_data ? JSON.parse(a.raw_data) : {};
              const bRaw = b.raw_data ? JSON.parse(b.raw_data) : {};
              aVal = aRaw["Resource"] || "";
              bVal = bRaw["Resource"] || "";
            } catch {
              aVal = "";
              bVal = "";
            }
            break;
          case "Data type":
            aVal = a.io_type || "";
            bVal = b.io_type || "";
            break;
          case "DCI":
            aVal = a.data_channel_id || "";
            bVal = b.data_channel_id || "";
            break;
          case "MQTT Tag":
            aVal = a.io_no || "";
            bVal = b.io_no || "";
            break;
          case "Description":
            aVal = a.description || "";
            bVal = b.description || "";
            break;
          default:
            return 0;
        }
        
        if (typeof aVal === "string") {
          aVal = aVal.toLowerCase();
          bVal = bVal.toLowerCase();
        }
        
        if (aVal < bVal) return sortDirection === "asc" ? -1 : 1;
        if (aVal > bVal) return sortDirection === "asc" ? 1 : -1;
        return 0;
      });
    }
    
    return filtered;
  }, [items, searchText, sortColumn, sortDirection]);

  const handleSort = (column: string) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortColumn(column);
      setSortDirection("asc");
    }
  };

  const handleDeleteItem = async (itemId: number) => {
    if (!confirm("정말 삭제하시겠습니까?")) return;

    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${apiBase}/iolist/items/${itemId}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: "삭제 실패" }));
        throw new Error(errorData.detail || "삭제 실패");
      }

      if (selectedHeader) {
        await loadItems(selectedHeader.id);
      }
      alert("항목이 삭제되었습니다.");
    } catch (e: any) {
      setError(e.message || "항목 삭제 실패");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteHeader = async (headerId: number) => {
    if (!confirm("IOLIST와 모든 항목을 삭제하시겠습니까?")) return;

    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${apiBase}/iolist/headers/${headerId}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: "삭제 실패" }));
        throw new Error(errorData.detail || "삭제 실패");
      }

      setSelectedHeader(null);
      setItems([]);
      setSelectedHeaders(new Set());
      await loadHeaders();
      await loadFilters();
      alert("IOLIST가 삭제되었습니다.");
    } catch (e: any) {
      setError(e.message || "IOLIST 삭제 실패");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectHeader = (headerId: number, index: number, e: React.MouseEvent) => {
    e.stopPropagation();
    const newSelected = new Set(selectedHeaders);
    
    if (e.shiftKey && lastSelectedIndex !== null) {
      // Shift 클릭: 범위 선택
      const start = Math.min(lastSelectedIndex, index);
      const end = Math.max(lastSelectedIndex, index);
      for (let i = start; i <= end; i++) {
        newSelected.add(headers[i].id);
      }
    } else {
      // 일반 클릭: 토글
      if (newSelected.has(headerId)) {
        newSelected.delete(headerId);
      } else {
        newSelected.add(headerId);
      }
    }
    
    setSelectedHeaders(newSelected);
    setLastSelectedIndex(index);
  };

  const handleSelectAllHeaders = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked) {
      setSelectedHeaders(new Set(headers.map(h => h.id)));
    } else {
      setSelectedHeaders(new Set());
    }
  };

  const handleDeleteSelectedHeaders = async () => {
    if (selectedHeaders.size === 0) {
      alert("삭제할 항목을 선택해주세요.");
      return;
    }
    
    if (!confirm(`선택한 ${selectedHeaders.size}개의 IOLIST를 삭제하시겠습니까?`)) return;

    setLoading(true);
    setError("");
    try {
      const deletePromises = Array.from(selectedHeaders).map(headerId =>
        fetch(`${apiBase}/iolist/headers/${headerId}`, { method: "DELETE" })
      );
      
      const results = await Promise.allSettled(deletePromises);
      const failed = results.filter(r => r.status === "rejected" || (r.status === "fulfilled" && !r.value.ok));
      
      if (failed.length > 0) {
        throw new Error(`${failed.length}개의 삭제가 실패했습니다.`);
      }

      setSelectedHeader(null);
      setItems([]);
      setSelectedHeaders(new Set());
      await loadHeaders();
      await loadFilters();
      alert(`${selectedHeaders.size}개의 IOLIST가 삭제되었습니다.`);
    } catch (e: any) {
      setError(e.message || "삭제 실패");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ width: "100%", height: "100vh", margin: 0, fontFamily: "system-ui, -apple-system, sans-serif", padding: "20px", boxSizing: "border-box", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <h1 style={{ marginTop: 0 }}>DP Manager - IOLIST 관리</h1>

      {/* 필터 및 IOLIST 목록 (같은 라인) */}
      <div style={{ display: "flex", gap: 20, marginBottom: 20, flex: "0 1 auto", minHeight: 0, overflow: "hidden" }}>
        {/* 필터 섹션 */}
        <div style={{ padding: 20, border: "1px solid #ddd", borderRadius: 8, background: "#f9f9f9", flexShrink: 0, width: "250px" }}>
          {/* 업로드 버튼 */}
          <div style={{ marginBottom: 20 }}>
            <label style={{ display: "block", marginBottom: 5, fontSize: 14, fontWeight: "bold" }}>엑셀 파일 업로드</label>
            <input
              type="file"
              accept=".xlsx,.xls"
              onChange={handleFileSelect}
              disabled={loading}
              style={{ width: "100%", padding: 8 }}
            />
            <small style={{ color: "#666", fontSize: 11, display: "block", marginTop: 5 }}>
              파일명 형식: H2567_IMO9991862_IOList_20260125.xlsx
            </small>
          </div>
          
          <h2 style={{ marginTop: 0, marginBottom: 15 }}>필터</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 15 }}>
            <div>
              <label style={{ display: "block", marginBottom: 5, fontSize: 14 }}>Hull Number</label>
              <select
                value={filterHullNo}
                onChange={(e) => setFilterHullNo(e.target.value)}
                style={{ width: "100%", padding: 8 }}
              >
                <option value="">전체</option>
                {filters.hull_nos.map((h) => (
                  <option key={h} value={h}>{h}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={{ display: "block", marginBottom: 5, fontSize: 14 }}>IMO Number</label>
              <select
                value={filterIMO}
                onChange={(e) => setFilterIMO(e.target.value)}
                style={{ width: "100%", padding: 8 }}
              >
                <option value="">전체</option>
                {filters.imos.map((i) => (
                  <option key={i} value={i}>{i}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={{ display: "block", marginBottom: 5, fontSize: 14 }}>날짜 키</label>
              <select
                value={filterDateKey}
                onChange={(e) => setFilterDateKey(e.target.value)}
                style={{ width: "100%", padding: 8 }}
              >
                <option value="">전체</option>
                {filters.date_keys.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>
            <button
              onClick={() => {
                setFilterHullNo("");
                setFilterIMO("");
                setFilterDateKey("");
              }}
              style={{ padding: "8px 16px", background: "#6c757d", color: "white", border: "none", borderRadius: 4, cursor: "pointer", marginTop: 10 }}
            >
              초기화
            </button>
          </div>
        </div>

        {/* IOLIST 헤더 목록 */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0, overflow: "hidden" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
          <h2 style={{ margin: 0 }}>IOLIST 목록</h2>
          {selectedHeaders.size > 0 && (
            <button
              onClick={handleDeleteSelectedHeaders}
              disabled={loading}
              style={{ padding: "8px 16px", background: "#dc3545", color: "white", border: "none", borderRadius: 4, cursor: "pointer" }}
            >
              선택 삭제 ({selectedHeaders.size})
            </button>
          )}
        </div>
        {loading && <p>로딩 중...</p>}
        {error && <p style={{ color: "crimson" }}>{error}</p>}
        <div style={{ border: "1px solid #ddd", borderRadius: 8, overflow: "auto", height: "180px", minHeight: "180px" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead style={{ background: "#f8f9fa" }}>
              <tr>
                <th style={{ padding: 12, textAlign: "center", borderBottom: "2px solid #ddd", width: "50px" }}>
                  <input
                    type="checkbox"
                    checked={headers.length > 0 && selectedHeaders.size === headers.length}
                    onChange={handleSelectAllHeaders}
                    onClick={(e) => e.stopPropagation()}
                  />
                </th>
                <th style={{ padding: 12, textAlign: "left", borderBottom: "2px solid #ddd" }}>Hull NO</th>
                <th style={{ padding: 12, textAlign: "left", borderBottom: "2px solid #ddd" }}>IMO</th>
                <th style={{ padding: 12, textAlign: "left", borderBottom: "2px solid #ddd" }}>날짜 키</th>
                <th style={{ padding: 12, textAlign: "left", borderBottom: "2px solid #ddd" }}>파일명</th>
                <th style={{ padding: 12, textAlign: "left", borderBottom: "2px solid #ddd" }}>항목 수</th>
                <th style={{ padding: 12, textAlign: "left", borderBottom: "2px solid #ddd" }}>생성일</th>
                <th style={{ padding: 12, textAlign: "left", borderBottom: "2px solid #ddd" }}>작업</th>
              </tr>
            </thead>
            <tbody>
              {headers.map((header, index) => (
                <tr
                  key={header.id}
                  style={{
                    background: selectedHeader?.id === header.id ? "#e7f3ff" : "white",
                    cursor: "pointer",
                  }}
                  onClick={() => handleHeaderSelect(header)}
                >
                  <td style={{ padding: 12, borderBottom: "1px solid #eee", textAlign: "center" }}>
                    <input
                      type="checkbox"
                      checked={selectedHeaders.has(header.id)}
                      onChange={() => {}}
                      onClick={(e) => handleSelectHeader(header.id, index, e)}
                      onMouseDown={(e) => e.stopPropagation()}
                    />
                  </td>
                  <td style={{ padding: 12, borderBottom: "1px solid #eee" }}>{header.hull_no}</td>
                  <td style={{ padding: 12, borderBottom: "1px solid #eee" }}>{header.imo}</td>
                  <td style={{ padding: 12, borderBottom: "1px solid #eee" }}>{header.date_key}</td>
                  <td style={{ padding: 12, borderBottom: "1px solid #eee" }}>{header.file_name}</td>
                  <td style={{ padding: 12, borderBottom: "1px solid #eee" }}>{header.item_count}</td>
                  <td style={{ padding: 12, borderBottom: "1px solid #eee" }}>
                    {new Date(header.created_at).toLocaleString("ko-KR")}
                  </td>
                  <td style={{ padding: 12, borderBottom: "1px solid #eee" }}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteHeader(header.id);
                      }}
                      style={{ padding: "4px 8px", background: "#dc3545", color: "white", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 12 }}
                    >
                      삭제
                    </button>
                  </td>
                </tr>
              ))}
              {headers.length === 0 && !loading && (
                <tr>
                  <td colSpan={8} style={{ padding: 20, textAlign: "center", color: "#999" }}>
                    IOLIST가 없습니다.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        </div>
      </div>

      {/* IOLIST 항목 GRID */}
      {selectedHeader && (
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0, overflow: "hidden" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
            <h2 style={{ marginTop: 0 }}>
              IOLIST 항목: {selectedHeader.hull_no} / {selectedHeader.imo} / {selectedHeader.date_key}
            </h2>
            <button
              onClick={async () => {
                try {
                  const res = await fetch(`${apiBase}/iolist/headers/${selectedHeader.id}/download-dp`);
                  if (!res.ok) {
                    throw new Error("DP 파일 다운로드 실패");
                  }
                  const blob = await res.blob();
                  const url = window.URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  const contentDisposition = res.headers.get("Content-Disposition");
                  const filename = contentDisposition
                    ? contentDisposition.split("filename=")[1].replace(/"/g, "")
                    : `DP_${selectedHeader.imo}_${new Date().toISOString().replace(/[:.]/g, "-")}.xml`;
                  a.download = filename;
                  document.body.appendChild(a);
                  a.click();
                  window.URL.revokeObjectURL(url);
                  document.body.removeChild(a);
                } catch (e: any) {
                  setError(e.message || "DP 파일 다운로드 실패");
                }
              }}
              disabled={loading}
              style={{ padding: "8px 16px", background: "#17a2b8", color: "white", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 14 }}
            >
              DP 파일 다운로드
            </button>
          </div>
          
          {/* 항목 필터 및 액션 (한 줄) */}
          <div style={{ padding: 15, border: "1px solid #ddd", borderRadius: 8, marginBottom: 20, background: "#f0f8ff", flexShrink: 0 }}>
            <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
              <button
                onClick={async () => {
                  if (!selectedHeader) {
                    setError("IOLIST를 먼저 선택해주세요.");
                    return;
                  }
                  await loadDevices(selectedHeader.id);
                  setEditingDevice({ device_name: "", protocol: "MQTT" });
                  setShowDeviceModal(true);
                }}
                disabled={loading}
                style={{ padding: "8px 16px", background: "#17a2b8", color: "white", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 14 }}
              >
                device 추가
              </button>
              <span style={{ color: "#666" }}>|</span>
              <button
                onClick={handleCreateClick}
                disabled={loading}
                style={{ padding: "8px 16px", background: "#28a745", color: "white", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 14 }}
              >
                새 항목 추가
              </button>
              <span style={{ color: "#666" }}>|</span>
              <input
                type="text"
                placeholder="검색..."
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                style={{ padding: "8px 12px", border: "1px solid #ddd", borderRadius: 4, fontSize: 14, minWidth: "200px" }}
              />
              <button
                onClick={() => setSearchText("")}
                disabled={!searchText}
                style={{ padding: "8px 12px", background: "#6c757d", color: "white", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 14 }}
                title="검색어 초기화"
              >
                초기화
              </button>
              <span style={{ color: "#666" }}>|</span>
              <label style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 14 }}>
                <input
                  type="checkbox"
                  checked={showDuplicates}
                  onChange={(e) => setShowDuplicates(e.target.checked)}
                />
                중복만 표시
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 14 }}>
                <input
                  type="checkbox"
                  checked={showMissingRequired}
                  onChange={(e) => setShowMissingRequired(e.target.checked)}
                />
                필수 값 없음만 표시
              </label>
            </div>
          </div>

          {/* 통계 정보 (제목 없음) */}
          {filteredAndSortedItems.length > 0 && (() => {
            const stats: ItemStatistics = {
              total: filteredAndSortedItems.length,
              by_device: {}
            };
            filteredAndSortedItems.forEach(item => {
              try {
                const rawData = item.raw_data ? JSON.parse(item.raw_data) : {};
                const device = rawData["Resource"] || "Unknown";
                stats.by_device[device] = (stats.by_device[device] || 0) + 1;
              } catch (e) {
                const device = "Unknown";
                stats.by_device[device] = (stats.by_device[device] || 0) + 1;
              }
            });
            return (
              <div style={{ padding: 15, border: "1px solid #ddd", borderRadius: 8, marginBottom: 20, background: "#e7f3ff", flexShrink: 0 }}>
                <div style={{ display: "flex", gap: 30, flexWrap: "wrap" }}>
                  <div>
                    <strong>총 개수:</strong> {stats.total}개
                  </div>
                  {Object.entries(stats.by_device).map(([device, count]) => (
                    <div key={device}>
                      <strong>{device}:</strong> {count}개
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}

          {/* 항목 GRID */}
          <div style={{ border: "1px solid #ddd", borderRadius: 8, overflow: "auto", flex: 1, minHeight: 0 }}>
            <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
              <colgroup>
                <col style={{ width: "60px" }} />
                <col style={{ width: "150px" }} />
                <col style={{ width: "120px" }} />
                <col style={{ width: "300px" }} />
                <col style={{ width: "250px" }} />
                <col style={{ width: "300px" }} />
                <col style={{ width: "150px" }} />
                <col style={{ width: "150px" }} />
              </colgroup>
              <thead style={{ background: "#f8f9fa", position: "sticky", top: 0, zIndex: 10 }}>
                <tr>
                  <th 
                    style={{ padding: 12, textAlign: "center", borderBottom: "2px solid #ddd", cursor: "pointer" }}
                    onClick={() => handleSort("#")}
                  >
                    # {sortColumn === "#" && (sortDirection === "asc" ? "↑" : "↓")}
                  </th>
                  <th 
                    style={{ padding: 12, textAlign: "left", borderBottom: "2px solid #ddd", cursor: "pointer" }}
                    onClick={() => handleSort("Device")}
                  >
                    Device {sortColumn === "Device" && (sortDirection === "asc" ? "↑" : "↓")}
                  </th>
                  <th 
                    style={{ padding: 12, textAlign: "left", borderBottom: "2px solid #ddd", cursor: "pointer" }}
                    onClick={() => handleSort("Data type")}
                  >
                    Data type {sortColumn === "Data type" && (sortDirection === "asc" ? "↑" : "↓")}
                  </th>
                  <th 
                    style={{ padding: 12, textAlign: "left", borderBottom: "2px solid #ddd", cursor: "pointer" }}
                    onClick={() => handleSort("DCI")}
                  >
                    DCI {sortColumn === "DCI" && (sortDirection === "asc" ? "↑" : "↓")}
                  </th>
                  <th 
                    style={{ padding: 12, textAlign: "left", borderBottom: "2px solid #ddd", cursor: "pointer" }}
                    onClick={() => handleSort("MQTT Tag")}
                  >
                    MQTT Tag {sortColumn === "MQTT Tag" && (sortDirection === "asc" ? "↑" : "↓")}
                  </th>
                  <th 
                    style={{ padding: 12, textAlign: "left", borderBottom: "2px solid #ddd", cursor: "pointer" }}
                    onClick={() => handleSort("Description")}
                  >
                    Description {sortColumn === "Description" && (sortDirection === "asc" ? "↑" : "↓")}
                  </th>
                  <th style={{ padding: 12, textAlign: "left", borderBottom: "2px solid #ddd" }}>상태</th>
                  <th style={{ padding: 12, textAlign: "left", borderBottom: "2px solid #ddd" }}>작업</th>
                </tr>
              </thead>
              <tbody>
                {filteredAndSortedItems.map((item, index) => {
                  const rawData = item.raw_data ? (() => {
                    try {
                      return JSON.parse(item.raw_data);
                    } catch {
                      return {};
                    }
                  })() : {};
                  const device = rawData["Resource"] || "-";
                  const dataType = rawData["Data type"] || item.io_type || "-";
                  
                  // 비정상 여부 확인
                  const isAbnormal = item.is_duplicate_data_channel_id || item.is_duplicate_mqtt_tag || 
                                     item.is_duplicate_description || item.has_missing_required;
                  const rowBgColor = isAbnormal ? "#ffe0e0" : "white";  // 연한 빨간색
                  
                  return (
                    <tr key={item.id} style={{ background: rowBgColor }}>
                      <>
                          <td style={{ 
                            padding: 12, 
                            borderBottom: "1px solid #eee",
                            textAlign: "center"
                          }}>
                            {index + 1}
                          </td>
                          <td style={{ 
                            padding: 12, 
                            borderBottom: "1px solid #eee",
                            wordBreak: "break-word",
                            whiteSpace: "normal"
                          }}>
                            {device}
                          </td>
                          <td style={{ 
                            padding: 12, 
                            borderBottom: "1px solid #eee",
                            wordBreak: "break-word",
                            whiteSpace: "normal"
                          }}>
                            {dataType}
                          </td>
                          <td style={{ 
                            padding: 12, 
                            borderBottom: "1px solid #eee",
                            wordBreak: "break-word",
                            whiteSpace: "normal"
                          }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                              <span style={{ flex: 1 }}>{item.data_channel_id || "-"}</span>
                              {item.is_duplicate_data_channel_id && (
                                <span style={{ color: "red", fontSize: 12, whiteSpace: "nowrap" }}>⚠️ 중복</span>
                              )}
                            </div>
                          </td>
                          <td style={{ 
                            padding: 12, 
                            borderBottom: "1px solid #eee",
                            wordBreak: "break-word",
                            whiteSpace: "normal"
                          }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                              <span style={{ flex: 1 }}>{item.io_no || "-"}</span>
                              {item.is_duplicate_mqtt_tag && (
                                <span style={{ color: "red", fontSize: 12, whiteSpace: "nowrap" }}>⚠️ 중복</span>
                              )}
                            </div>
                          </td>
                          <td style={{ 
                            padding: 12, 
                            borderBottom: "1px solid #eee",
                            wordBreak: "break-word",
                            whiteSpace: "normal"
                          }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                              <span style={{ flex: 1 }}>{item.description || "-"}</span>
                              {item.is_duplicate_description && (
                                <span style={{ color: "red", fontSize: 12, whiteSpace: "nowrap" }}>⚠️ 중복</span>
                              )}
                            </div>
                          </td>
                          <td style={{ 
                            padding: 12, 
                            borderBottom: "1px solid #eee",
                            wordBreak: "break-word"
                          }}>
                            {item.has_missing_required && (
                              <span style={{ color: "orange", fontSize: 12 }}>⚠️ 필수 값 없음</span>
                            )}
                            {!item.has_missing_required && item.is_duplicate_data_channel_id && (
                              <span style={{ color: "red", fontSize: 12 }}>⚠️ DataChannelId 중복</span>
                            )}
                            {!item.has_missing_required && item.is_duplicate_mqtt_tag && (
                              <span style={{ color: "red", fontSize: 12 }}>⚠️ MQTT Tag 중복</span>
                            )}
                            {!item.has_missing_required && item.is_duplicate_description && (
                              <span style={{ color: "red", fontSize: 12 }}>⚠️ Description 중복</span>
                            )}
                            {!item.has_missing_required && !item.is_duplicate_data_channel_id && 
                             !item.is_duplicate_description && !item.is_duplicate_mqtt_tag && (
                              <span style={{ color: "green", fontSize: 12 }}>✓ 정상</span>
                            )}
                          </td>
                          <td style={{ padding: 12, borderBottom: "1px solid #eee" }}>
                            <button
                              onClick={() => handleEditClick(item)}
                              style={{ padding: "4px 8px", background: "#ffc107", color: "black", border: "none", borderRadius: 4, cursor: "pointer", marginRight: 5, fontSize: 12 }}
                            >
                              수정
                            </button>
                            <button
                              onClick={() => handleDeleteItem(item.id)}
                              disabled={loading}
                              style={{ padding: "4px 8px", background: "#dc3545", color: "white", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 12 }}
                            >
                              삭제
                            </button>
                          </td>
                      </>
                    </tr>
                  );
                })}
                {filteredAndSortedItems.length === 0 && !loading && (
                  <tr>
                    <td colSpan={8} style={{ padding: 20, textAlign: "center", color: "#999" }}>
                      항목이 없습니다.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 수정 모달 */}
      {showEditModal && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(0, 0, 0, 0.5)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 1000
        }} onClick={() => {
          setShowEditModal(false);
          setEditingItem(null);
          setEditingRawData({});
        }}>
          <div style={{
            background: "white",
            borderRadius: 8,
            padding: 20,
            maxWidth: "90%",
            maxHeight: "90%",
            overflow: "auto",
            width: "800px"
          }} onClick={(e) => e.stopPropagation()}>
            <h2 style={{ marginTop: 0, marginBottom: 20 }}>{editingItem ? "항목 수정" : "새 항목 추가"}</h2>
            
            <div style={{ display: "flex", flexDirection: "column", gap: 15 }}>
              {Object.keys(editingRawData).map((key) => {
                const isRequired = ["Resource", "Data type", "RuleNaming", "Level 1", "Measure"].includes(key);
                const isResource = key === "Resource";
                const isDataType = key === "Data type";
                
                return (
                  <div key={key}>
                    <label style={{ display: "block", marginBottom: 5, fontWeight: "bold", fontSize: 14 }}>
                      {key} {isRequired && <span style={{ color: "red" }}>(필수)</span>}
                    </label>
                    {isResource ? (
                      <select
                        value={editingRawData[key] || ""}
                        onChange={(e) => {
                          setEditingRawData({
                            ...editingRawData,
                            [key]: e.target.value
                          });
                        }}
                        style={{ width: "100%", padding: 8, border: "1px solid #ddd", borderRadius: 4 }}
                      >
                        <option value="">선택하세요</option>
                        {devices.map((device) => (
                          <option key={device.id} value={device.device_name}>
                            {device.device_name}
                          </option>
                        ))}
                      </select>
                    ) : isDataType ? (
                      <select
                        value={editingRawData[key] || ""}
                        onChange={(e) => {
                          setEditingRawData({
                            ...editingRawData,
                            [key]: e.target.value
                          });
                        }}
                        style={{ width: "100%", padding: 8, border: "1px solid #ddd", borderRadius: 4 }}
                      >
                        <option value="">선택하세요</option>
                        <option value="DECIMAL">DECIMAL</option>
                        <option value="FLOAT">FLOAT</option>
                        <option value="INT">INT</option>
                        <option value="STRING">STRING</option>
                        <option value="BOOL">BOOL</option>
                      </select>
                    ) : (
                      <input
                        type="text"
                        value={editingRawData[key] || ""}
                        onChange={(e) => {
                          setEditingRawData({
                            ...editingRawData,
                            [key]: e.target.value
                          });
                        }}
                        style={{ width: "100%", padding: 8, border: "1px solid #ddd", borderRadius: 4 }}
                      />
                    )}
                  </div>
                );
              })}
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 20 }}>
              <button
                onClick={() => {
                  setShowEditModal(false);
                  setEditingItem(null);
                  setEditingRawData({});
                }}
                style={{ padding: "8px 16px", background: "#6c757d", color: "white", border: "none", borderRadius: 4, cursor: "pointer" }}
              >
                취소
              </button>
              <button
                onClick={handleSaveItem}
                disabled={loading}
                style={{ padding: "8px 16px", background: "#007bff", color: "white", border: "none", borderRadius: 4, cursor: "pointer" }}
              >
                저장
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Device 추가/수정 모달 */}
      {showDeviceModal && editingDevice && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(0, 0, 0, 0.5)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 1000
        }} onClick={() => {
          setShowDeviceModal(false);
          setEditingDevice(null);
        }}>
          <div style={{
            background: "white",
            borderRadius: 8,
            padding: 20,
            maxWidth: "600px",
            width: "90%",
            maxHeight: "80vh",
            overflow: "auto"
          }} onClick={(e) => e.stopPropagation()}>
            <h2 style={{ marginTop: 0, marginBottom: 20 }}>
              {editingDevice.id ? "Device 수정" : "Device 추가"}
            </h2>
            
            {/* 등록된 Device 리스트 */}
            {devices.length > 0 && (
              <div style={{ marginBottom: 20, padding: 15, background: "#f8f9fa", borderRadius: 4, border: "1px solid #dee2e6" }}>
                <h3 style={{ marginTop: 0, marginBottom: 10, fontSize: 16, fontWeight: "bold" }}>
                  등록된 Device 목록 ({devices.length}개)
                </h3>
                <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: "200px", overflowY: "auto" }}>
                  {devices.map((device) => (
                    <div
                      key={device.id}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "8px 12px",
                        background: "white",
                        borderRadius: 4,
                        border: "1px solid #dee2e6"
                      }}
                    >
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: "bold", fontSize: 14, marginBottom: 2 }}>
                          {device.device_name}
                        </div>
                        <div style={{ fontSize: 12, color: "#666" }}>
                          Protocol: {device.protocol}
                        </div>
                      </div>
                      <div style={{ display: "flex", gap: 5 }}>
                        <button
                          onClick={() => {
                            setEditingDevice({
                              id: device.id,
                              device_name: device.device_name,
                              protocol: device.protocol
                            });
                          }}
                          style={{
                            padding: "4px 8px",
                            background: "#007bff",
                            color: "white",
                            border: "none",
                            borderRadius: 4,
                            cursor: "pointer",
                            fontSize: 12
                          }}
                        >
                          수정
                        </button>
                        <button
                          onClick={async () => {
                            if (!selectedHeader) return;
                            if (!confirm(`"${device.device_name}" Device를 삭제하시겠습니까?`)) return;
                            
                            setLoading(true);
                            try {
                              const res = await fetch(
                                `${apiBase}/iolist/headers/${selectedHeader.id}/devices/${device.id}`,
                                { method: "DELETE" }
                              );
                              if (res.ok) {
                                await loadDevices(selectedHeader.id);
                                alert("Device가 삭제되었습니다.");
                              } else {
                                const errorData = await res.json().catch(() => ({ detail: "실패" }));
                                throw new Error(errorData.detail || "실패");
                              }
                            } catch (e: any) {
                              setError(e.message || "삭제 실패");
                            } finally {
                              setLoading(false);
                            }
                          }}
                          disabled={loading}
                          style={{
                            padding: "4px 8px",
                            background: "#dc3545",
                            color: "white",
                            border: "none",
                            borderRadius: 4,
                            cursor: "pointer",
                            fontSize: 12
                          }}
                        >
                          삭제
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            <div style={{ display: "flex", flexDirection: "column", gap: 15 }}>
              <div>
                <label style={{ display: "block", marginBottom: 5, fontWeight: "bold", fontSize: 14 }}>
                  Device Name (필수)
                </label>
                <input
                  type="text"
                  value={editingDevice.device_name || ""}
                  onChange={(e) => setEditingDevice({ ...editingDevice, device_name: e.target.value })}
                  style={{ width: "100%", padding: 8, border: "1px solid #ddd", borderRadius: 4 }}
                  placeholder="예: IAS, VDR 등"
                />
              </div>
              <div>
                <label style={{ display: "block", marginBottom: 5, fontWeight: "bold", fontSize: 14 }}>
                  Protocol (필수)
                </label>
                <select
                  value={editingDevice.protocol || "MQTT"}
                  onChange={(e) => setEditingDevice({ ...editingDevice, protocol: e.target.value })}
                  style={{ width: "100%", padding: 8, border: "1px solid #ddd", borderRadius: 4 }}
                >
                  <option value="MQTT">MQTT</option>
                  <option value="NMEA">NMEA</option>
                  <option value="OPCUA">OPCUA</option>
                  <option value="OPCDA">OPCDA</option>
                  <option value="MODBUS">MODBUS</option>
                </select>
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 20 }}>
              <button
                onClick={() => {
                  setShowDeviceModal(false);
                  setEditingDevice(null);
                }}
                style={{ padding: "8px 16px", background: "#6c757d", color: "white", border: "none", borderRadius: 4, cursor: "pointer" }}
              >
                취소
              </button>
              <button
                onClick={async () => {
                  if (!selectedHeader || !editingDevice) return;
                  
                  if (!editingDevice.device_name.trim()) {
                    alert("Device Name을 입력해주세요.");
                    return;
                  }
                  
                  setLoading(true);
                  setError("");
                  try {
                    const url = editingDevice.id
                      ? `${apiBase}/iolist/headers/${selectedHeader.id}/devices/${editingDevice.id}`
                      : `${apiBase}/iolist/headers/${selectedHeader.id}/devices`;
                    const method = editingDevice.id ? "PUT" : "POST";
                    
                    const res = await fetch(url, {
                      method: method,
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({
                        device_name: editingDevice.device_name,
                        protocol: editingDevice.protocol
                      }),
                    });

                    if (!res.ok) {
                      const errorData = await res.json().catch(() => ({ detail: "실패" }));
                      throw new Error(errorData.detail || "실패");
                    }

                    setShowDeviceModal(false);
                    setEditingDevice(null);
                    await loadDevices(selectedHeader.id);
                    alert(editingDevice.id ? "Device가 수정되었습니다." : "Device가 추가되었습니다.");
                  } catch (e: any) {
                    setError(e.message || "실패");
                  } finally {
                    setLoading(false);
                  }
                }}
                disabled={loading}
                style={{ padding: "8px 16px", background: "#007bff", color: "white", border: "none", borderRadius: 4, cursor: "pointer" }}
              >
                저장
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
