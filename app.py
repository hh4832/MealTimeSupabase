import hashlib
from datetime import date, datetime

import pandas as pd
import streamlit as st
from supabase import Client, create_client


APP_TITLE = "7 月吃飯時間統計"

YEAR = 2026
START_DATE = date(YEAR, 7, 1)
END_DATE = date(YEAR, 7, 31)
SLOTS = ["午餐", "晚餐"]
EXPECTED_COLUMNS = ["name", "pin_hash", "day", "slot", "updated_at"]


@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.strip().encode("utf-8")).hexdigest()


def all_days():
    return pd.date_range(START_DATE, END_DATE, freq="D").date


def day_label(d: date) -> str:
    weekday_map = ["一", "二", "三", "四", "五", "六", "日"]
    return f"{d.strftime('%m/%d')}（{weekday_map[d.weekday()]}）"


def normalize_df(data, columns=None) -> pd.DataFrame:
    if columns is None:
        columns = EXPECTED_COLUMNS
    if not data:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(data)
    for col in columns:
        if col not in df.columns:
            df[col] = pd.Series(dtype="object")
    return df[columns]


def load_all(sb: Client) -> pd.DataFrame:
    res = (
        sb.table("availability")
        .select("name, pin_hash, day, slot, updated_at")
        .order("day")
        .order("slot")
        .order("name")
        .execute()
    )
    return normalize_df(res.data, EXPECTED_COLUMNS)


def load_user(sb: Client, name: str, pin: str) -> pd.DataFrame:
    pin_hash = hash_pin(pin)
    res = (
        sb.table("availability")
        .select("day, slot")
        .eq("name", name.strip())
        .eq("pin_hash", pin_hash)
        .execute()
    )
    return normalize_df(res.data, ["day", "slot"])


def replace_user_availability(sb: Client, name: str, pin: str, selected_pairs):
    name = name.strip()
    pin_hash = hash_pin(pin)
    now = datetime.now().isoformat(timespec="seconds")

    # 先刪除該使用者舊資料，再寫入新資料。這樣取消勾選也會生效。
    (
        sb.table("availability")
        .delete()
        .eq("name", name)
        .eq("pin_hash", pin_hash)
        .execute()
    )

    rows = [
        {
            "name": name,
            "pin_hash": pin_hash,
            "day": d,
            "slot": s,
            "created_at": now,
            "updated_at": now,
        }
        for d, s in selected_pairs
    ]

    if rows:
        sb.table("availability").insert(rows).execute()


def delete_user(sb: Client, name: str, pin: str) -> int:
    name = name.strip()
    pin_hash = hash_pin(pin)

    existing = (
        sb.table("availability")
        .select("id")
        .eq("name", name)
        .eq("pin_hash", pin_hash)
        .execute()
    )
    n = len(existing.data or [])

    (
        sb.table("availability")
        .delete()
        .eq("name", name)
        .eq("pin_hash", pin_hash)
        .execute()
    )

    return n


def overview_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["日期", "時段", "可出席人數", "可出席名單"])

    grouped = (
        df.groupby(["day", "slot"])["name"]
        .apply(lambda x: sorted(set(x)))
        .reset_index(name="names")
    )
    grouped["可出席人數"] = grouped["names"].apply(len)
    grouped["可出席名單"] = grouped["names"].apply(lambda xs: "、".join(xs))
    grouped["日期"] = pd.to_datetime(grouped["day"]).dt.date.apply(day_label)
    grouped["時段"] = grouped["slot"]

    slot_order = {"午餐": 0, "晚餐": 1}
    grouped["slot_order"] = grouped["slot"].map(slot_order)

    return grouped.sort_values(
        ["可出席人數", "day", "slot_order"],
        ascending=[False, True, True],
    )[["日期", "時段", "可出席人數", "可出席名單"]]


def participant_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["姓名", "填寫數量", "最後更新"])

    out = (
        df.groupby("name")
        .agg(填寫數量=("slot", "count"), 最後更新=("updated_at", "max"))
        .reset_index()
        .rename(columns={"name": "姓名"})
        .sort_values(["填寫數量", "姓名"], ascending=[False, True])
    )
    return out


def render_slot_grid(sb: Client, name: str, pin: str):
    user_df = load_user(sb, name, pin)
    existing = set(zip(user_df["day"].astype(str), user_df["slot"].astype(str))) if not user_df.empty else set()

    st.write("勾選你可以吃飯的時間：")
    selected = []

    header_cols = st.columns([1.6, 1, 1])
    header_cols[0].markdown("**日期**")
    header_cols[1].markdown("**午餐**")
    header_cols[2].markdown("**晚餐**")

    for d in all_days():
        cols = st.columns([1.6, 1, 1])
        cols[0].write(day_label(d))
        d_str = d.isoformat()

        for i, slot in enumerate(SLOTS, start=1):
            key_source = f"{name.strip()}_{hash_pin(pin)}_{d_str}_{slot}"
            checked = (d_str, slot) in existing
            if cols[i].checkbox(slot, value=checked, key=key_source, label_visibility="collapsed"):
                selected.append((d_str, slot))

    if st.button("儲存我的時間", type="primary"):
        replace_user_availability(sb, name, pin, selected)
        st.success(f"已儲存：{name.strip()}，共 {len(selected)} 個時段。")
        st.rerun()


def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="🍽️", layout="wide")
    st.title(APP_TITLE)
    st.caption("填寫 7/1–7/31 的午餐、晚餐可出席時間。用姓名＋編輯 PIN 可以修改或刪除自己的資料。")

    try:
        sb = get_supabase()
    except Exception as exc:
        st.error("無法讀取 Supabase 設定。請確認 `.streamlit/secrets.toml` 或 Streamlit Cloud Secrets 是否已設定。")
        st.code(
            'SUPABASE_URL = "https://你的-project-id.supabase.co"\n'
            'SUPABASE_KEY = "你的 publishable key 或 anon public key"',
            language="toml",
        )
        st.exception(exc)
        st.stop()

    tab_fill, tab_overview, tab_delete = st.tabs(["填寫 / 修改", "總覽", "刪除自己的資料"])

    with tab_fill:
        st.subheader("填寫或修改我的時間")
        c1, c2 = st.columns([2, 1])
        with c1:
            name = st.text_input("姓名", placeholder="例如：Howard")
        with c2:
            pin = st.text_input("編輯 PIN", type="password", placeholder="自己設定 4–8 碼即可")

        if not name.strip() or not pin.strip():
            st.info("請先輸入姓名與編輯 PIN。之後用同一組姓名＋PIN 即可修改。")
        elif len(pin.strip()) < 4:
            st.warning("建議 PIN 至少 4 碼。")
        else:
            render_slot_grid(sb, name, pin)

    with tab_overview:
        st.subheader("最多人可以的時間")
        try:
            df_all = load_all(sb)
        except Exception as exc:
            st.error("讀取 Supabase 資料失敗。請檢查 table、RLS policy、SUPABASE_URL、SUPABASE_KEY。")
            st.exception(exc)
            st.stop()

        ov = overview_table(df_all)
        ps = participant_summary(df_all)

        m1, m2 = st.columns(2)
        m1.metric("已填寫人數", df_all["name"].nunique() if not df_all.empty else 0)
        m2.metric("總可出席時段數", len(df_all))

        if ov.empty:
            st.info("目前還沒有人填寫。")
        else:
            st.dataframe(ov, use_container_width=True, hide_index=True)
            max_n = int(ov["可出席人數"].max())
            best = ov[ov["可出席人數"] == max_n]
            st.markdown(f"**目前最佳交集：{max_n} 人可出席**")
            st.dataframe(best, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("已填寫名單")
        st.dataframe(ps, use_container_width=True, hide_index=True)

    with tab_delete:
        st.subheader("刪除自己的資料")
        del_name = st.text_input("姓名", key="del_name")
        del_pin = st.text_input("編輯 PIN", type="password", key="del_pin")

        if st.button("刪除我的全部資料"):
            if not del_name.strip() or not del_pin.strip():
                st.error("請輸入姓名與編輯 PIN。")
            else:
                n = delete_user(sb, del_name, del_pin)
                if n > 0:
                    st.success(f"已刪除 {del_name.strip()} 的 {n} 筆資料。")
                    st.rerun()
                else:
                    st.warning("找不到符合的資料。請確認姓名與 PIN 是否相同。")


if __name__ == "__main__":
    main()
