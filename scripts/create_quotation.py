"""Create the official sales quotation (XSBJD) for 用友东方集团 (CUST0001)
with all 26 new materials, then submit + audit."""
import asyncio
import json
import u9_mcp.server as srv

MATS = [f"1.02.001.0007.{n:05d}" for n in range(6, 32)]  # .00006 .. .00031


async def main():
    entry = []
    for num in MATS:
        entry.append({
            "FMaterialId": {"FNumber": num},
            "FUnitID": {"FNumber": "Pcs"},
            "FQty": 1,
            "FPrice": 0.01,
            "FTaxPrice": 0.01,
            "FTaxRate": 13,
        })

    model = {
        "FBillTypeID": {"FNumber": "XSBJD01_SYS"},
        "FSaleOrgId": {"FNumber": "100"},
        "FCUSTID": {"FNumber": "CUST0001"},
        "FQUOTATIONENTRY": entry,
    }

    print(f"=== Saving quotation with {len(entry)} lines ===")
    save = await srv._post_raw("save", "SAL_Quotation", model)
    st = srv._result_status(save, "save")
    print("SAVE:", json.dumps(st, ensure_ascii=False))
    if not st.get("success"):
        print("SAVE FAILED -> abort")
        return

    bill_id = st.get("id")
    print(f"\n=== Submit bill id={bill_id} ===")
    sub = await srv._post_raw("submit", "SAL_Quotation", {"Ids": bill_id})
    print("SUBMIT:", json.dumps(srv._result_status(sub, "submit"), ensure_ascii=False))

    print(f"\n=== Audit bill id={bill_id} ===")
    aud = await srv._post_raw("audit", "SAL_Quotation", {"Ids": bill_id})
    print("AUDIT:", json.dumps(srv._result_status(aud, "audit"), ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
