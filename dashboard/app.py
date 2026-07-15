"""Industrial operations console for SmartValve AI Twin."""

# ruff: noqa: E501 -- embedded CSS/HTML is intentionally kept readable as complete rules.

from __future__ import annotations

import json
from datetime import datetime
from html import escape

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from smartvalve import MODEL_VERSION, __version__
from smartvalve.config import env_bool
from smartvalve.network_twin.model import LINKS, NODE_COORDINATES
from smartvalve.service.client import (
    ApiClientError,
    RemoteTwinRun,
    SkabView,
    SmartValveApiClient,
)

FAULT_LABELS = {
    "正常基线": "normal",
    "全局摩擦增长": "friction",
    "局部卡涩": "stiction",
    "行程受阻": "obstruction",
    "执行器退化": "actuator_degradation",
    "位置传感器漂移": "sensor_drift",
}

COLORS = {
    "ink": "#E8F0F8",
    "muted": "#8EA3B7",
    "grid": "#24364A",
    "panel": "#101D2D",
    "cyan": "#31C7D7",
    "blue": "#4C8DFF",
    "green": "#3DDC97",
    "amber": "#FFB547",
    "red": "#FF5D6C",
    "purple": "#A78BFA",
}

SOURCE_LABELS = {
    "simulation": "S0 · 可复现仿真",
    "cranfield_real_actuator": "S1 · Cranfield 真实执行器台架",
    "skab_real_water_loop": "S1 · SKAB 真实水循环台架",
    "desktop_rig": "S2 · 自有桌面样机",
    "enterprise_valve": "S3 候选 · 企业声明数据",
}


def _finite_column(frame: pd.DataFrame, name: str, fallback: np.ndarray) -> np.ndarray:
    """Return a finite numeric series for browser-side replay."""

    if name not in frame:
        return fallback.astype(float)
    values = pd.to_numeric(frame[name], errors="coerce").to_numpy(dtype=float)
    finite = np.isfinite(values)
    if not finite.any():
        return fallback.astype(float)
    values = pd.Series(values).interpolate(limit_direction="both").to_numpy(dtype=float)
    return np.where(np.isfinite(values), values, fallback).astype(float)


def _valve_replay_payload(run: RemoteTwinRun, max_points: int = 180) -> list[dict[str, float]]:
    """Downsample a full-stroke record for the animated digital-twin scene."""

    frame = run.current_data
    stride = max(1, int(np.ceil(len(frame) / max_points)))
    sampled = frame.iloc[::stride].copy()
    position = _finite_column(sampled, "position_pct", np.zeros(len(sampled)))
    command = _finite_column(sampled, "command_pct", position)
    current = _finite_column(sampled, "motor_current_a", np.zeros(len(sampled)))
    flow_fallback = 12.0 * np.clip(position / 100.0, 0.0, 1.0) ** 1.8
    flow = _finite_column(sampled, "flow_lpm", flow_fallback)
    timestamp = _finite_column(
        sampled,
        "timestamp_s",
        np.arange(len(sampled), dtype=float) / max(run.current_quality.sampling_hz, 1.0),
    )
    return [
        {
            "t": round(float(t), 3),
            "p": round(float(np.clip(p, 0.0, 100.0)), 2),
            "c": round(float(np.clip(c, 0.0, 100.0)), 2),
            "i": round(float(max(i, 0.0)), 3),
            "f": round(float(max(f, 0.0)), 3),
        }
        for t, p, c, i, f in zip(timestamp, position, command, current, flow, strict=True)
    ]


def _actuator_twin_animation(run: RemoteTwinRun, asset_id: str) -> None:
    """Render a truthful Cranfield electromechanical-actuator replay without hydraulics."""

    frame = run.current_data
    stride = max(1, int(np.ceil(len(frame) / 180)))
    sampled = frame.iloc[::stride].copy()
    position = _finite_column(sampled, "position_pct", np.zeros(len(sampled)))
    command = _finite_column(sampled, "command_pct", position)
    current = _finite_column(sampled, "motor_current_a", np.zeros(len(sampled)))
    timestamp = _finite_column(
        sampled,
        "timestamp_s",
        np.arange(len(sampled), dtype=float) / max(run.current_quality.sampling_hz, 1.0),
    )
    payload = [
        {
            "t": round(float(t), 3),
            "p": round(float(np.clip(p, 0.0, 100.0)), 2),
            "c": round(float(np.clip(c, 0.0, 100.0)), 2),
            "i": round(float(max(i, 0.0)), 3),
        }
        for t, p, c, i in zip(timestamp, position, command, current, strict=True)
    ]
    peak_current = max((item["i"] for item in payload), default=1.0)
    start = run.diagnosis.abnormal_start_pct
    end = run.diagnosis.abnormal_end_pct
    abnormal_start = -1.0 if start is None else float(start)
    abnormal_end = -1.0 if end is None else float(end)
    status, tone, _ = _status_style(run.diagnosis.ne107_status)
    status_color = {
        "red": "#ff5d6c",
        "amber": "#ffb547",
        "blue": "#4c8dff",
        "green": "#3ddc97",
    }[tone]
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    source = escape(_source_badge(str(frame["source"].iloc[0])))
    finding = escape(run.diagnosis.primary_finding)
    asset = escape(asset_id)
    st.iframe(
        f"""
<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
*{{box-sizing:border-box}}html,body{{margin:0;background:transparent;color:#e8f0f8;font-family:Inter,"Segoe UI",sans-serif;overflow:hidden}}
.scene{{position:relative;height:500px;border:1px solid #243b52;border-radius:10px;overflow:hidden;background:radial-gradient(circle at 50% 52%,rgba(49,199,215,.13),transparent 30%),linear-gradient(135deg,#0b1726,#08121f 58%,#0c1b2b)}}
.scene:before{{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(70,112,145,.06) 1px,transparent 1px),linear-gradient(90deg,rgba(70,112,145,.06) 1px,transparent 1px);background-size:34px 34px}}
.top{{position:absolute;z-index:5;left:22px;right:22px;top:18px;display:flex;justify-content:space-between;align-items:flex-start}}.kicker{{font-size:10px;letter-spacing:.2em;color:#5e829f;font-weight:800}}h2{{font-size:19px;margin:5px 0 3px}}.sub{{font-size:11px;color:#7793aa}}.state{{display:flex;gap:9px;align-items:center;border:1px solid {status_color}55;background:{status_color}0d;padding:8px 11px;border-radius:5px;color:{status_color};font-size:11px;font-weight:800;letter-spacing:.08em}}.state i{{width:8px;height:8px;border-radius:50%;background:{status_color};box-shadow:0 0 14px {status_color}}}
svg{{position:absolute;inset:78px 0 84px;width:100%;height:338px}}.rail{{filter:drop-shadow(0 12px 13px #0009)}}.screw{{stroke-dasharray:7 10;animation:screw 1.1s linear infinite}}.motor-rotor{{transform-box:fill-box;transform-origin:center;animation:rotor 2s linear infinite}}.scan{{animation:scan 3.2s linear infinite}}.label{{font-size:10px;letter-spacing:.12em;fill:#66859e}}.value{{font-size:15px;font-weight:700;fill:#e8f0f8}}.warn{{fill:{status_color};opacity:.13}}.alarm{{fill:none;stroke:{status_color};stroke-width:3;opacity:0}}.alarm.on{{animation:alarm 1s ease-out infinite}}
.readouts{{position:absolute;z-index:5;left:24px;bottom:24px;display:flex;gap:32px}}.readout small{{display:block;color:#66859e;font-size:9px;letter-spacing:.13em;margin-bottom:3px}}.readout b{{font:600 19px "Segoe UI"}}.readout em{{font-style:normal;color:#6f8aa2;font-size:10px;margin-left:3px}}.finding{{position:absolute;z-index:5;right:23px;bottom:22px;max-width:390px;border-left:2px solid {status_color};padding:4px 0 4px 12px;text-align:right}}.finding small{{display:block;color:#66859e;font-size:9px;letter-spacing:.13em}}.finding b{{font-size:12px;color:#c7d7e5}}.timeline{{position:absolute;left:24px;right:24px;bottom:7px;height:2px;background:#1e3448}}.timeline span{{display:block;height:100%;width:0;background:linear-gradient(90deg,#31c7d7,#4c8dff)}}
@keyframes screw{{to{{stroke-dashoffset:-34}}}}@keyframes rotor{{to{{transform:rotate(360deg)}}}}@keyframes scan{{from{{transform:translateX(-300px)}}to{{transform:translateX(1280px)}}}}@keyframes alarm{{0%{{r:47;opacity:.8}}100%{{r:72;opacity:0}}}}
</style></head><body><div class="scene">
<div class="top"><div><div class="kicker">PHYSICAL EMA / 25 HZ FULL-STROKE REPLAY</div><h2>{asset} · 机电执行器内部状态透视</h2><div class="sub">{source} · 指令、位置与电流均来自公开物理台架</div></div><div class="state"><i></i>{status}</div></div>
<svg viewBox="0 0 1280 338" role="img" aria-label="Cranfield机电执行器实测回放动画"><defs><linearGradient id="metal"><stop stop-color="#60798b"/><stop offset=".45" stop-color="#20384a"/><stop offset="1" stop-color="#0a1723"/></linearGradient><linearGradient id="car"><stop stop-color="#1b5268"/><stop offset="1" stop-color="#102738"/></linearGradient></defs>
<path class="scan" d="M0 50V300" stroke="#31c7d7" opacity=".13"/><g class="rail"><rect x="120" y="164" width="1040" height="88" rx="12" fill="url(#metal)" stroke="#536d80" stroke-width="3"/><rect x="154" y="188" width="972" height="38" rx="18" fill="#07131f" stroke="#29465a"/><line x1="171" y1="207" x2="1109" y2="207" stroke="#78a4ba" stroke-width="11"/><line class="screw" x1="171" y1="207" x2="1109" y2="207" stroke="#d3e3eb" stroke-width="4"/></g>
<g transform="translate(65 207)"><rect x="-42" y="-53" width="84" height="106" rx="13" fill="#142b3d" stroke="#526d80" stroke-width="3"/><circle class="motor-rotor" r="25" fill="#081724" stroke="#31c7d7" stroke-width="2"/><path d="M0-17V17M-17 0H17M-12-12L12 12M12-12L-12 12" stroke="#31c7d7" stroke-width="2"/><text y="78" text-anchor="middle" class="label">SERVO MOTOR</text></g>
<rect id="faultBand" class="warn" x="160" y="145" width="0" height="126" rx="8"/><g id="carriage"><rect x="-55" y="-72" width="110" height="144" rx="12" fill="url(#car)" stroke="#58b7c8" stroke-width="3"/><path d="M-37-44H37M-37 44H37" stroke="#94c4d0" stroke-width="5"/><circle id="alarm" class="alarm" r="47"/><text y="96" text-anchor="middle" class="label">BALL-SCREW CARRIAGE</text></g>
<g transform="translate(1195 82)"><circle r="43" fill="#0b1926" stroke="#2b455b" stroke-width="7"/><circle id="ampArc" r="43" fill="none" stroke="#ffb547" stroke-width="7" stroke-linecap="round" transform="rotate(-90)" stroke-dasharray="270"/><text id="ampText" y="5" text-anchor="middle" class="value">0 A</text><text y="66" text-anchor="middle" class="label">MOTOR CURRENT</text></g>
<g transform="translate(85 82)"><circle r="43" fill="#0b1926" stroke="#2b455b" stroke-width="7"/><circle id="posArc" r="43" fill="none" stroke="#31c7d7" stroke-width="7" stroke-linecap="round" transform="rotate(-90)" stroke-dasharray="270"/><text id="posText" y="5" text-anchor="middle" class="value">0%</text><text y="66" text-anchor="middle" class="label">MEASURED POSITION</text></g>
<text x="155" y="292" class="label">0% RETRACTED</text><text x="1125" y="292" text-anchor="end" class="label">100% EXTENDED</text></svg>
<div class="readouts"><div class="readout"><small>SETPOINT</small><b id="cmdValue">0.0</b><em>%</em></div><div class="readout"><small>POSITION</small><b id="posValue">0.0</b><em>%</em></div><div class="readout"><small>CURRENT</small><b id="ampValue">0.0</b><em>A</em></div><div class="readout"><small>TIME</small><b id="timeValue">0.0</b><em>s</em></div></div><div class="finding"><small>GENERIC VALVEDNA FINDING</small><b>{finding}</b></div><div class="timeline"><span id="progress"></span></div></div>
<script>const frames={data_json},peak={max(peak_current, 0.001):.6f},a0={abnormal_start:.3f},a1={abnormal_end:.3f},duration=12,$=id=>document.getElementById(id);if(a0>=0&&a1>=a0){{$('faultBand').setAttribute('x',160+9.65*a0);$('faultBand').setAttribute('width',Math.max(8,9.65*(a1-a0)))}}function text(id,v){{$(id).textContent=v}}function tick(now){{const phase=(now/1000%duration)/duration,d=frames[Math.min(frames.length-1,Math.floor(phase*frames.length))]||{{t:0,p:0,c:0,i:0}},p=d.p; $('carriage').setAttribute('transform',`translate(${{160+9.65*p}} 207)`);$('posArc').style.strokeDashoffset=String(270*(1-p/100));$('ampArc').style.strokeDashoffset=String(270*(1-Math.min(1,d.i/peak)));$('alarm').classList.toggle('on',a0>=0&&p>=a0&&p<=a1);text('posText',p.toFixed(0)+'%');text('ampText',d.i.toFixed(2)+' A');text('cmdValue',d.c.toFixed(1));text('posValue',p.toFixed(1));text('ampValue',d.i.toFixed(3));text('timeValue',d.t.toFixed(2));$('progress').style.width=(phase*100)+'%';requestAnimationFrame(tick)}}requestAnimationFrame(tick);</script></body></html>
""",
        height=500,
        width="stretch",
        tab_index=-1,
    )


def _valve_twin_animation(run: RemoteTwinRun, asset_id: str) -> None:
    """Render a data-driven animated valve cutaway in an isolated component."""

    if str(run.current_data["source"].iloc[0]) == "cranfield_real_actuator":
        _actuator_twin_animation(run, asset_id)
        return

    payload = _valve_replay_payload(run)
    peak_current = max((item["i"] for item in payload), default=1.0)
    max_flow = max((item["f"] for item in payload), default=1.0)
    start = run.diagnosis.abnormal_start_pct
    end = run.diagnosis.abnormal_end_pct
    abnormal_start = -1.0 if start is None else float(start)
    abnormal_end = -1.0 if end is None else float(end)
    status, tone, _ = _status_style(run.diagnosis.ne107_status)
    status_color = {
        "red": "#ff5d6c",
        "amber": "#ffb547",
        "blue": "#4c8dff",
        "green": "#3ddc97",
    }[tone]
    source = _source_badge(str(run.current_data["source"].iloc[0]))
    finding = escape(run.diagnosis.primary_finding)
    asset = escape(asset_id)
    source_text = escape(source)
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    st.iframe(
        f"""
<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><style>
*{{box-sizing:border-box}}html,body{{margin:0;background:transparent;color:#e8f0f8;font-family:Inter,"Segoe UI",sans-serif;overflow:hidden}}
.scene{{position:relative;height:500px;border:1px solid #243b52;border-radius:10px;overflow:hidden;
background:radial-gradient(circle at 50% 47%,rgba(49,199,215,.12),transparent 27%),linear-gradient(135deg,#0b1726,#08121f 58%,#0c1b2b)}}
.scene:before{{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(70,112,145,.06) 1px,transparent 1px),linear-gradient(90deg,rgba(70,112,145,.06) 1px,transparent 1px);background-size:34px 34px;mask-image:linear-gradient(to bottom,#000,transparent 92%)}}
.top{{position:absolute;z-index:5;left:22px;right:22px;top:18px;display:flex;justify-content:space-between;align-items:flex-start}}
.kicker{{font-size:10px;letter-spacing:.2em;color:#5e829f;font-weight:800}}h2{{font-size:19px;margin:5px 0 3px;letter-spacing:-.02em}}.sub{{font-size:11px;color:#7793aa}}
.state{{display:flex;gap:9px;align-items:center;border:1px solid {status_color}55;background:{status_color}0d;padding:8px 11px;border-radius:5px;color:{status_color};font-size:11px;font-weight:800;letter-spacing:.08em}}
.state i{{width:8px;height:8px;border-radius:50%;background:{status_color};box-shadow:0 0 14px {status_color};animation:blink 1.5s infinite}}
.readouts{{position:absolute;z-index:5;left:24px;bottom:23px;display:flex;gap:28px}}.readout small{{display:block;color:#66859e;font-size:9px;letter-spacing:.13em;margin-bottom:3px}}.readout b{{font:600 19px "Segoe UI";color:#eff8ff}}.readout em{{font-style:normal;color:#6f8aa2;font-size:10px;margin-left:3px}}
.finding{{position:absolute;z-index:5;right:23px;bottom:22px;max-width:390px;border-left:2px solid {status_color};padding:4px 0 4px 12px;text-align:right}}.finding small{{display:block;color:#66859e;font-size:9px;letter-spacing:.13em}}.finding b{{font-size:12px;color:#c7d7e5}}
.timeline{{position:absolute;z-index:6;left:24px;right:24px;bottom:7px;height:2px;background:#1e3448}}.timeline span{{display:block;height:100%;width:0;background:linear-gradient(90deg,#31c7d7,#4c8dff);box-shadow:0 0 10px #31c7d7}}
svg{{position:absolute;inset:66px 0 82px;width:100%;height:350px}}.shell{{filter:url(#shadow)}}.flowline{{stroke-dasharray:3 21;filter:url(#cyanGlow)}}.particle{{fill:#c4fbff;filter:url(#cyanGlow)}}
.rotor{{transform-box:fill-box;transform-origin:center;animation:rotor 3s linear infinite}}.scan{{animation:scan 3.2s linear infinite}}.alarm-ring{{opacity:0}}.alarm-ring.on{{animation:alarm 1s ease-out infinite}}.label{{font-size:10px;letter-spacing:.12em;fill:#66859e}}.value{{font-size:15px;font-weight:700;fill:#e8f0f8}}
@keyframes blink{{50%{{opacity:.35}}}}@keyframes rotor{{to{{transform:rotate(360deg)}}}}@keyframes scan{{from{{transform:translateX(-280px)}}to{{transform:translateX(1280px)}}}}@keyframes alarm{{0%{{r:55;opacity:.8}}100%{{r:88;opacity:0}}}}
</style></head><body>
<div class="scene">
  <div class="top"><div><div class="kicker">LIVE DIGITAL TWIN / FULL-STROKE REPLAY</div><h2>{asset} · 阀门内部状态透视</h2><div class="sub">{source_text} · 动画由实际回放点驱动</div></div><div class="state"><i></i>{status}</div></div>
  <svg viewBox="0 0 1280 350" role="img" aria-label="数据驱动阀门数字孪生动画">
    <defs>
      <linearGradient id="pipe" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#314a5e"/><stop offset=".42" stop-color="#132a3d"/><stop offset=".58" stop-color="#0a1e30"/><stop offset="1" stop-color="#2a4154"/></linearGradient>
      <linearGradient id="water"><stop offset="0" stop-color="#173a54"/><stop offset=".5" stop-color="#0d6580"/><stop offset="1" stop-color="#173a54"/></linearGradient>
      <radialGradient id="metal"><stop offset="0" stop-color="#617b8d"/><stop offset=".45" stop-color="#273d4e"/><stop offset="1" stop-color="#0a1723"/></radialGradient>
      <filter id="cyanGlow"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      <filter id="shadow"><feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="#000" flood-opacity=".55"/></filter>
      <clipPath id="bore"><rect x="58" y="151" width="1164" height="72" rx="36"/></clipPath>
    </defs>
    <g opacity=".6"><path d="M0 56H1280" stroke="#1f3447"/><path d="M0 286H1280" stroke="#1f3447"/><path class="scan" d="M0 68V282" stroke="#31c7d7" opacity=".14"/></g>
    <g class="shell"><rect x="38" y="130" width="1204" height="115" rx="57" fill="url(#pipe)" stroke="#486176" stroke-width="2"/><rect x="58" y="151" width="1164" height="72" rx="36" fill="url(#water)" stroke="#1e718a"/></g>
    <g clip-path="url(#bore)"><path id="flowline" class="flowline" d="M62 187H1218" stroke="#62e9f3" stroke-width="4" opacity=".65"/><g id="particles"></g></g>
    <g><path d="M557 123L577 97H703L723 123" fill="#162b3c" stroke="#526b7e"/><circle cx="640" cy="187" r="69" fill="url(#metal)" stroke="#6b8294" stroke-width="4"/><circle cx="640" cy="187" r="52" fill="#0d3548" stroke="#31c7d7" stroke-opacity=".45"/>
      <circle id="alarmRing" class="alarm-ring" cx="640" cy="187" r="58" fill="none" stroke="#ff5d6c" stroke-width="3"/>
      <g id="disk"><ellipse cx="640" cy="187" rx="8" ry="48" fill="#bdcfda" stroke="#e5f2f8" stroke-width="2"/><line x1="640" y1="137" x2="640" y2="237" stroke="#7892a4"/></g>
      <rect x="632" y="82" width="16" height="52" rx="5" fill="#8299a8"/><rect x="570" y="25" width="140" height="65" rx="11" fill="#172b3c" stroke="#526b7e" stroke-width="2"/><circle cx="608" cy="57" r="20" fill="#0c1926" stroke="#31c7d7" stroke-opacity=".65"/><g class="rotor"><path d="M608 41V73M592 57H624M597 46L619 68M619 46L597 68" stroke="#31c7d7" stroke-width="2"/></g><text x="642" y="53" class="label">ELECTRIC</text><text x="642" y="70" class="value" style="font-size:11px">ACTUATOR</text>
    </g>
    <g><circle cx="177" cy="72" r="42" fill="#0b1926" stroke="#2b455b" stroke-width="7"/><circle id="posArc" cx="177" cy="72" r="42" fill="none" stroke="#31c7d7" stroke-width="7" stroke-linecap="round" transform="rotate(-90 177 72)" stroke-dasharray="264"/><text id="posText" x="177" y="77" text-anchor="middle" class="value">0%</text><text x="177" y="126" text-anchor="middle" class="label">VALVE POSITION</text></g>
    <g><circle cx="1103" cy="72" r="42" fill="#0b1926" stroke="#2b455b" stroke-width="7"/><circle id="ampArc" cx="1103" cy="72" r="42" fill="none" stroke="#ffb547" stroke-width="7" stroke-linecap="round" transform="rotate(-90 1103 72)" stroke-dasharray="264"/><text id="ampText" x="1103" y="77" text-anchor="middle" class="value">0 A</text><text x="1103" y="126" text-anchor="middle" class="label">MOTOR CURRENT</text></g>
    <g><text x="82" y="277" class="label">UPSTREAM</text><text x="82" y="300" class="value">350 kPa</text><text x="1198" y="277" text-anchor="end" class="label">DOWNSTREAM</text><text x="1198" y="300" text-anchor="end" class="value">250 kPa</text><text id="flowText" x="640" y="286" text-anchor="middle" class="value" fill="#63e8f2">0.0 L/min</text><text id="timeText" x="640" y="307" text-anchor="middle" class="label">T + 0.00 s</text></g>
  </svg>
  <div class="readouts"><div class="readout"><small>COMMAND</small><b id="cmdValue">0.0</b><em>%</em></div><div class="readout"><small>POSITION</small><b id="posValue">0.0</b><em>%</em></div><div class="readout"><small>FLOW</small><b id="flowValue">0.0</b><em>L/min</em></div><div class="readout"><small>CURRENT</small><b id="ampValue">0.0</b><em>A</em></div></div>
  <div class="finding"><small>VALVEDNA PRIMARY FINDING</small><b>{finding}</b></div><div class="timeline"><span id="progress"></span></div>
</div>
<script>
const frames={data_json}, peakCurrent={peak_current:.6f}, maxFlow={max(max_flow, 0.001):.6f};
const abnormalStart={abnormal_start:.3f}, abnormalEnd={abnormal_end:.3f}, duration=12;
const $=id=>document.getElementById(id), particles=$('particles');
for(let n=0;n<24;n++){{const c=document.createElementNS('http://www.w3.org/2000/svg','circle');c.setAttribute('r',n%3===0?2.7:1.6);c.setAttribute('class','particle');c.dataset.phase=String(n/24);particles.appendChild(c)}}
function setText(id,value){{$(id).textContent=value}}
function tick(now){{
  const phase=(now/1000%duration)/duration, index=Math.min(frames.length-1,Math.floor(phase*frames.length));
  const d=frames[index]||{{t:0,p:0,c:0,i:0,f:0}}, p=d.p, openness=p/100, flowRatio=Math.min(1,d.f/maxFlow);
  $('disk').setAttribute('transform',`rotate(${{p*.9}} 640 187)`);
  $('flowline').style.strokeDashoffset=String(-now*(.012+.05*flowRatio));$('flowline').style.opacity=String(.12+.72*flowRatio);
  particles.querySelectorAll('circle').forEach((c,n)=>{{const q=(Number(c.dataset.phase)+now*(.000025+.00014*flowRatio))%1;c.setAttribute('cx',60+1160*q);c.setAttribute('cy',187+Math.sin(q*24+n)*20);c.style.opacity=String(.08+.85*flowRatio)}});
  $('posArc').style.strokeDashoffset=String(264*(1-openness));$('ampArc').style.strokeDashoffset=String(264*(1-Math.min(1,d.i/peakCurrent)));
  const alarm=abnormalStart>=0&&p>=abnormalStart&&p<=abnormalEnd;$('alarmRing').classList.toggle('on',alarm);
  setText('posText',p.toFixed(0)+'%');setText('ampText',d.i.toFixed(2)+' A');setText('flowText',d.f.toFixed(2)+' L/min');setText('timeText','T + '+d.t.toFixed(2)+' s');
  setText('cmdValue',d.c.toFixed(1));setText('posValue',p.toFixed(1));setText('flowValue',d.f.toFixed(2));setText('ampValue',d.i.toFixed(3));$('progress').style.width=(phase*100)+'%';
  requestAnimationFrame(tick)
}}requestAnimationFrame(tick);
</script></body></html>
""",
        height=500,
        width="stretch",
        tab_index=-1,
    )


def _network_twin_animation(run: RemoteTwinRun) -> None:
    """Render animated hydraulic propagation using WNTR result values."""

    coordinates = {"R1": (105, 235), "J1": (340, 235), "J2": (610, 235), "J3": (960, 92), "J4": (960, 378)}
    paths = {
        "P1": "M105 235 L340 235",
        "V1": "M340 235 L610 235",
        "P2": "M610 235 L960 92",
        "P3": "M610 235 L960 378",
    }
    pressure = {"R1": 60.0, **run.network.fault_pressure_m}
    max_flow = max(run.network.fault_flow_lps.values(), default=1.0)
    pipe_markup: list[str] = []
    for link, path in paths.items():
        flow = max(float(run.network.fault_flow_lps.get(link, 0.0)), 0.01)
        duration = float(np.clip(7.0 * max_flow / flow, 1.7, 9.5))
        particles = "".join(
            f'<circle r="{3 if index % 2 else 2}" class="water-dot"><animateMotion dur="{duration:.2f}s" begin="-{duration * index / 7:.2f}s" repeatCount="indefinite" path="{path}"/></circle>'
            for index in range(7)
        )
        pipe_markup.append(
            f'<path d="{path}" class="pipe-shadow"/><path d="{path}" class="pipe"/><path d="{path}" class="flow" style="animation-duration:{duration:.2f}s"/>{particles}'
        )
    node_markup: list[str] = []
    for node, (x, y) in coordinates.items():
        node_pressure = float(pressure[node])
        affected = node in run.network.affected_nodes
        tone = "#ff5d6c" if affected else ("#ffb547" if node_pressure < 40 else "#3ddc97")
        pulse = '<circle r="28" class="node-pulse"/>' if affected else ""
        node_markup.append(
            f'<g transform="translate({x} {y})">{pulse}<circle r="20" fill="#0b1926" stroke="{tone}" stroke-width="3"/><circle r="7" fill="{tone}" class="node-core"/><text y="-34" text-anchor="middle" class="node-name">{node}</text><text y="45" text-anchor="middle" class="node-pressure">{node_pressure:.1f} m</text></g>'
        )
    pipes = "".join(pipe_markup)
    nodes = "".join(node_markup)
    affected_text = escape(" / ".join(run.network.affected_nodes) or "NONE")
    engine = escape(run.network.engine)
    angle = 0.9 * run.network.available_travel_pct
    st.iframe(
        f"""
<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
*{{box-sizing:border-box}}html,body{{margin:0;background:transparent;color:#e8f0f8;font-family:Inter,"Segoe UI",sans-serif;overflow:hidden}}.network{{position:relative;height:455px;border:1px solid #243b52;border-radius:10px;overflow:hidden;background:radial-gradient(circle at 52% 50%,rgba(76,141,255,.13),transparent 31%),linear-gradient(135deg,#0b1726,#08121f)}}
.network:before{{content:"";position:absolute;inset:0;background-image:radial-gradient(#28455c 1px,transparent 1px);background-size:22px 22px;opacity:.34}}.head{{position:absolute;z-index:3;top:18px;left:22px;right:22px;display:flex;justify-content:space-between}}.kicker{{font-size:10px;letter-spacing:.19em;color:#5e829f;font-weight:800}}h2{{font-size:18px;margin:5px 0}}.engine{{font-size:10px;color:#6f8da2;text-align:right}}.impact{{font-size:25px;color:#f1f7fc;font-weight:650}}.impact em{{font-style:normal;font-size:11px;color:#708aa1}}
svg{{position:absolute;inset:61px 0 38px;width:100%;height:356px}}.pipe-shadow{{fill:none;stroke:#050b12;stroke-width:25;stroke-linecap:round}}.pipe{{fill:none;stroke:#29455a;stroke-width:17;stroke-linecap:round}}.flow{{fill:none;stroke:#31c7d7;stroke-width:3;stroke-dasharray:2 16;opacity:.65;animation:stream linear infinite}}.water-dot{{fill:#baf9ff;filter:drop-shadow(0 0 5px #31c7d7)}}.node-name{{fill:#9bb1c3;font-size:11px;font-weight:800;letter-spacing:.12em}}.node-pressure{{fill:#dce9f3;font-size:12px;font-weight:650}}.node-core{{animation:core 1.8s ease-in-out infinite}}.node-pulse{{fill:none;stroke:#ff5d6c;stroke-width:2;animation:pulse 1.4s ease-out infinite}}.valve-body{{fill:#101f2d;stroke:#ffb547;stroke-width:3;filter:drop-shadow(0 0 8px #ffb54755)}}.disk{{stroke:#f4d29b;stroke-width:7;stroke-linecap:round}}.legend{{position:absolute;left:23px;bottom:16px;display:flex;gap:20px;color:#6d879d;font-size:9px;letter-spacing:.09em}}.legend i{{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px}}.affected{{position:absolute;right:22px;bottom:15px;font-size:10px;color:#7f99ae}}.affected b{{color:#ffb547}}
@keyframes stream{{to{{stroke-dashoffset:-180}}}}@keyframes core{{50%{{opacity:.38}}}}@keyframes pulse{{from{{r:23;opacity:.85}}to{{r:49;opacity:0}}}}
</style></head><body><div class="network"><div class="head"><div><div class="kicker">HYDRAULIC CONSEQUENCE / LIVE FLOW FIELD</div><h2>V1 阀门异常 · 管网影响传播</h2></div><div class="engine"><span class="impact">{run.network.impact_score:.1f}<em> / 100</em></span><br>{engine}</div></div>
<svg viewBox="0 0 1100 460" role="img" aria-label="WNTR管网影响动态可视化"><defs><filter id="glow"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>{pipes}{nodes}
<g transform="translate(475 235)"><circle r="36" class="valve-body"/><g transform="rotate({angle:.2f})"><line x1="0" y1="-27" x2="0" y2="27" class="disk"/></g><text y="-48" text-anchor="middle" class="node-name">V1 · {run.network.available_travel_pct:.1f}% TRAVEL</text><text y="58" text-anchor="middle" class="node-pressure">K = {run.network.equivalent_loss_coefficient:.1f}</text></g></svg>
<div class="legend"><span><i style="background:#3ddc97"></i>服务正常</span><span><i style="background:#ffb547"></i>裕度降低</span><span><i style="background:#ff5d6c"></i>低于服务阈值</span><span><i style="background:#31c7d7"></i>粒子速度对应流量</span></div><div class="affected">AFFECTED NODES&nbsp; <b>{affected_text}</b></div></div></body></html>
""",
        height=455,
        width="stretch",
        tab_index=-1,
    )


def _plot_style(figure: go.Figure, *, height: int = 390) -> go.Figure:
    figure.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(7,17,31,.46)",
        font={"color": COLORS["ink"], "family": "Inter, Segoe UI, sans-serif", "size": 12},
        title={"font": {"size": 15, "color": COLORS["ink"]}, "x": 0.01},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
            "font": {"color": COLORS["muted"]},
        },
        margin={"l": 48, "r": 24, "t": 62, "b": 42},
        hoverlabel={"bgcolor": "#0B1726", "font_color": COLORS["ink"]},
    )
    figure.update_xaxes(gridcolor=COLORS["grid"], zerolinecolor=COLORS["grid"])
    figure.update_yaxes(gridcolor=COLORS["grid"], zerolinecolor=COLORS["grid"])
    return figure


def _time_series_figure(run: RemoteTwinRun) -> go.Figure:
    data = run.current_data
    figure = make_subplots(specs=[[{"secondary_y": True}]])
    figure.add_trace(
        go.Scatter(
            x=data["timestamp_s"],
            y=data["command_pct"],
            name="开度指令",
            line={"color": COLORS["muted"], "dash": "dot", "width": 1.5},
        ),
        secondary_y=False,
    )
    figure.add_trace(
        go.Scatter(
            x=data["timestamp_s"],
            y=data["position_pct"],
            name="实际阀位",
            line={"color": COLORS["cyan"], "width": 2.5},
        ),
        secondary_y=False,
    )
    figure.add_trace(
        go.Scatter(
            x=data["timestamp_s"],
            y=data["motor_current_a"],
            name="电机电流",
            line={"color": COLORS["amber"], "width": 1.6},
            fill="tozeroy",
            fillcolor="rgba(255,181,71,.09)",
        ),
        secondary_y=True,
    )
    figure.update_yaxes(title_text="行程 / %", range=[-3, 105], secondary_y=False)
    figure.update_yaxes(title_text="电流 / A", rangemode="tozero", secondary_y=True)
    figure.update_xaxes(title_text="测试时间 / s")
    figure.update_layout(title="全行程响应 · Command / Position / Current", hovermode="x unified")
    return _plot_style(figure)


def _signature_figure(run: RemoteTwinRun) -> go.Figure:
    baseline = run.signature.baseline_signature
    current = run.signature.current_signature
    figure = go.Figure()
    series = (
        (baseline["current_open_a"], "基线 · 开启", COLORS["muted"], "dash", 1.8),
        (baseline["current_close_a"], "基线 · 关闭", COLORS["muted"], "dot", 1.8),
        (current["current_open_a"], "当前 · 开启", COLORS["red"], "solid", 2.8),
        (current["current_close_a"], "当前 · 关闭", COLORS["amber"], "solid", 2.2),
    )
    for values, name, color, dash, width in series:
        figure.add_trace(
            go.Scatter(
                x=current["position_pct"],
                y=values,
                name=name,
                line={"color": color, "dash": dash, "width": width},
            )
        )
    start = run.signature.abnormal_start_pct
    end = run.signature.abnormal_end_pct
    if start is not None and end is not None:
        figure.add_vrect(
            x0=start,
            x1=end,
            fillcolor=COLORS["red"],
            opacity=0.10,
            line_width=1,
            line_color=COLORS["red"],
            annotation_text="异常边界",
            annotation_font_color=COLORS["red"],
        )
    figure.update_layout(
        title="ValveDNA · 基线与当前签名叠加",
        xaxis_title="阀位 / %",
        yaxis_title="电流 / A",
        hovermode="x unified",
    )
    return _plot_style(figure)


def _network_figure(run: RemoteTwinRun) -> go.Figure:
    figure = go.Figure()
    for link_name, start, end in LINKS:
        x0, y0 = NODE_COORDINATES[start]
        x1, y1 = NODE_COORDINATES[end]
        is_valve = link_name == "V1"
        figure.add_trace(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line={
                    "color": COLORS["amber"] if is_valve else "#354A60",
                    "width": 8 if is_valve else 5,
                },
                hovertext=f"{link_name} · {'受控阀门' if is_valve else '管段'}",
                hoverinfo="text",
                showlegend=False,
            )
        )

    node_names = list(NODE_COORDINATES)
    pressures = [
        60.0 if node == "R1" else run.network.fault_pressure_m[node] for node in node_names
    ]
    labels = []
    for node, pressure in zip(node_names, pressures, strict=True):
        if node == "R1":
            labels.append(f"{node}<br><b>60.0 m</b>")
        else:
            delta = run.network.pressure_delta_m[node]
            labels.append(f"{node}<br><b>{pressure:.1f} m</b><br>Δ {delta:.1f}")
    figure.add_trace(
        go.Scatter(
            x=[NODE_COORDINATES[node][0] for node in node_names],
            y=[NODE_COORDINATES[node][1] for node in node_names],
            mode="markers+text",
            text=labels,
            textposition="top center",
            textfont={"color": COLORS["ink"], "size": 11},
            marker={
                "size": [30 if node == "R1" else 25 for node in node_names],
                "color": pressures,
                "colorscale": [[0, COLORS["red"]], [0.5, COLORS["amber"]], [1, COLORS["green"]]],
                "cmin": 20,
                "cmax": 60,
                "line": {"color": "#DDE9F5", "width": 1.5},
                "colorbar": {"title": "压力 / m", "thickness": 10},
            },
            hovertext=labels,
            hoverinfo="text",
            showlegend=False,
        )
    )
    figure.update_xaxes(visible=False, range=[-0.3, 3.55])
    figure.update_yaxes(visible=False, range=[-1.7, 1.7], scaleanchor="x", scaleratio=1)
    figure.update_layout(title="水网拓扑 · V1 系统影响传播")
    return _plot_style(figure, height=440)


def _pressure_figure(run: RemoteTwinRun) -> go.Figure:
    nodes = list(run.network.baseline_pressure_m)
    figure = go.Figure(
        [
            go.Bar(
                name="健康基线",
                x=nodes,
                y=[run.network.baseline_pressure_m[node] for node in nodes],
                marker_color=COLORS["cyan"],
                opacity=0.55,
            ),
            go.Bar(
                name="当前状态",
                x=nodes,
                y=[run.network.fault_pressure_m[node] for node in nodes],
                marker_color=COLORS["amber"],
            ),
        ]
    )
    figure.add_hline(
        y=run.network.service_pressure_threshold_m,
        line_dash="dash",
        line_color=COLORS["red"],
        annotation_text="服务阈值",
        annotation_font_color=COLORS["red"],
    )
    figure.update_layout(barmode="group", title="节点服务压力 · Baseline vs Current")
    figure.update_yaxes(title_text="压力 / m")
    return _plot_style(figure, height=440)


def _skab_figure(result: SkabView) -> go.Figure:
    frame = result.data
    figure = make_subplots(specs=[[{"secondary_y": True}]])
    figure.add_trace(
        go.Scatter(
            x=frame["timestamp_s"],
            y=frame["FlowLPM"],
            name="真实流量",
            line={"color": COLORS["cyan"], "width": 1.8},
        ),
        secondary_y=False,
    )
    figure.add_trace(
        go.Scatter(
            x=frame["timestamp_s"],
            y=result.score,
            name="无监督异常分",
            line={"color": COLORS["amber"], "width": 1.5},
        ),
        secondary_y=True,
    )
    anomaly = frame["anomaly"].astype(bool)
    if anomaly.any():
        figure.add_vrect(
            x0=float(frame.loc[anomaly, "timestamp_s"].min()),
            x1=float(frame.loc[anomaly, "timestamp_s"].max()),
            fillcolor=COLORS["red"],
            opacity=0.08,
            line_width=0,
            annotation_text="官方异常区间",
            annotation_font_color=COLORS["red"],
        )
    figure.add_hline(
        y=result.threshold,
        secondary_y=True,
        line_dash="dot",
        line_color=COLORS["purple"],
        annotation_text="固定阈值",
    )
    figure.update_yaxes(title_text="流量 / L·min⁻¹", secondary_y=False)
    figure.update_yaxes(title_text="异常分", secondary_y=True)
    figure.update_xaxes(title_text="实验时间 / s")
    figure.update_layout(title="SKAB Valve 1 · 真实水循环实验回放", hovermode="x unified")
    return _plot_style(figure, height=420)


def _status_style(status: str) -> tuple[str, str, str]:
    if status.startswith("F"):
        return "FAILURE", "red", "需要立即处理"
    if status.startswith("M"):
        return "MAINTENANCE", "amber", "安排状态检修"
    if status.startswith("S"):
        return "OUT OF SPEC", "blue", "核查运行条件"
    return "NORMAL", "green", "无需干预"


def _status_banner(run: RemoteTwinRun) -> None:
    label, tone, action = _status_style(run.diagnosis.ne107_status)
    if run.diagnosis.decision_state == "needs_review":
        action = "人工复核 · 禁止自动派单"
    st.markdown(
        f"""
        <div class="status-strip {tone}">
          <div><span class="signal"></span><b>{label}</b><small>NAMUR NE 107 风格状态</small></div>
          <div class="status-finding"><small>PRIMARY FINDING</small><b>{run.diagnosis.primary_finding}</b></div>
          <div class="status-action"><small>RESPONSE</small><b>{action}</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _source_badge(source: str) -> str:
    return SOURCE_LABELS.get(source, source)


def _report_markdown(run: RemoteTwinRun, asset_id: str) -> str:
    affected = "、".join(run.network.affected_nodes) or "无"
    start = run.diagnosis.abnormal_start_pct
    end = run.diagnosis.abnormal_end_pct
    interval = f"{start:.0f}–{end:.0f}%" if start is not None and end is not None else "未定位"
    source = str(run.current_data["source"].iloc[0])
    source_boundary = {
        "simulation": "可复现仿真，不是厂商产品实测。",
        "cranfield_real_actuator": "公开真实机电执行器台架，不是水阀或伟隆产品。",
    }.get(source, "外部数据，必须核验设备与工况元数据。")
    return f"""# SmartValve AI Twin 状态诊断报告

- 资产：{asset_id}
- 数据证据等级：{_source_badge(source)}
- 数据 SHA-256：{run.current_quality.data_sha256}
- ValveDNA 相似度：{run.signature.similarity_pct:.1f}%
- 数据质量：{run.current_quality.score:.1f}/100
- 健康分：{run.diagnosis.health_score:.1f}/100
- 状态：{run.diagnosis.ne107_status}
- 主要发现：{run.diagnosis.primary_finding}
- 异常行程区间：{interval}
- 管网影响分：{run.network.impact_score:.1f}/100
- 受影响节点：{affected}

## 建议动作

{run.diagnosis.recommendation}

## 证据边界

{source_boundary} 可用行程到水力损失的映射尚未按具体阀门 Kv/Cv 标定。
"""


def _fleet_frame(run: RemoteTwinRun) -> pd.DataFrame:
    health = run.diagnosis.health_score
    impact = run.network.impact_score
    rows = [
        ("DEMO-FAC-001", "合成出厂检测线", "DN300 蝶阀", 98.2, 0, "NORMAL"),
        ("DEMO-FAC-002", "合成出厂检测线", "DN500 蝶阀", 95.7, 0, "NORMAL"),
        (
            "DEMO-QD-007",
            "合成青岛水网",
            "DN400 电动阀",
            health,
            impact,
            _status_style(run.diagnosis.ne107_status)[0],
        ),
        ("DEMO-QD-008", "合成青岛水网", "DN600 闸阀", 91.4, 8, "NORMAL"),
        ("DEMO-QD-011", "合成青岛水网", "DN300 蝶阀", 79.6, 12, "MAINTENANCE"),
        ("DEMO-WS-021", "合成加压泵站", "DN800 蝶阀", 93.1, 4, "NORMAL"),
        ("DEMO-WS-022", "合成加压泵站", "DN800 蝶阀", 86.3, 28, "MAINTENANCE"),
        ("PUBLIC-EMA-03", "公共数据验证", "Cranfield EMA", 92.8, 0, "EXTERNAL DATA"),
    ]
    return pd.DataFrame(
        rows, columns=["资产编号", "站点", "设备类型", "健康分", "系统影响", "状态"]
    )


def _fleet_map(frame: pd.DataFrame) -> go.Figure:
    positions = [(0, 2), (1, 2), (2.5, 1.5), (3.5, 1.7), (3.1, 0.5), (1, 0), (2, -0.2), (4.2, -0.4)]
    color_map = {
        "NORMAL": COLORS["green"],
        "MAINTENANCE": COLORS["amber"],
        "FAILURE": COLORS["red"],
        "OUT OF SPEC": COLORS["blue"],
        "EXTERNAL DATA": COLORS["purple"],
    }
    figure = go.Figure()
    for index, row in frame.iterrows():
        x, y = positions[index]
        figure.add_trace(
            go.Scatter(
                x=[x],
                y=[y],
                mode="markers+text",
                text=[row["资产编号"]],
                textposition="bottom center",
                marker={
                    "size": 18 + float(row["系统影响"]) * 0.25,
                    "color": color_map.get(row["状态"], COLORS["muted"]),
                    "line": {"color": "#DCE8F5", "width": 1},
                },
                hovertemplate=(
                    f"<b>{row['资产编号']}</b><br>{row['站点']}<br>"
                    f"健康 {row['健康分']:.1f}<br>系统影响 {row['系统影响']:.1f}<extra></extra>"
                ),
                showlegend=False,
            )
        )
    figure.update_xaxes(visible=False, range=[-0.5, 4.8])
    figure.update_yaxes(visible=False, range=[-0.8, 2.5])
    figure.update_layout(title="资产状态地图 · 颜色代表设备状态，尺寸代表系统影响")
    return _plot_style(figure, height=390)


def _api_client() -> SmartValveApiClient:
    access_token: str | None = None
    try:
        if env_bool("SMARTVALVE_TRUST_PROXY_ACCESS_TOKEN", False):
            forwarded = st.context.headers.get("X-SmartValve-Access-Token", "").strip()
            access_token = forwarded or None
        else:
            authorization = st.context.headers.get("Authorization", "").strip()
            scheme, separator, token = authorization.partition(" ")
            if separator and scheme.lower() == "bearer" and token.strip():
                access_token = token.strip()
    except (AttributeError, RuntimeError):
        pass
    return SmartValveApiClient(access_token=access_token)


@st.cache_data(show_spinner=False, ttl=60)
def _source_status() -> dict[str, object]:
    return _api_client().sources()


@st.cache_data(show_spinner=False, ttl=15)
def _runtime_status() -> dict[str, object]:
    return _api_client().readiness()


@st.cache_data(show_spinner=False, ttl=15)
def _audit_status() -> dict[str, object]:
    return _api_client().verify_audit_chain()


@st.cache_data(show_spinner=False)
def _load_public_cranfield() -> RemoteTwinRun:
    return _api_client().cranfield_validation_sample()


@st.cache_data(show_spinner=False)
def _load_skab_validation() -> SkabView:
    return _api_client().validate_skab()


@st.cache_data(show_spinner=False, ttl=60)
def _load_benchmark(profile: str = "full") -> dict[str, object]:
    return _api_client().validation_benchmark(profile)


@st.cache_data(show_spinner=False, ttl=60)
def _load_cranfield_validation() -> dict[str, object]:
    return _api_client().validation_cranfield()


@st.cache_data(show_spinner=False)
def _load_diagnostic_pdf(run_id: str) -> bytes:
    return _api_client().diagnostic_pdf(run_id)


def _load_run(
    analysis_source: str,
    fault_type: str,
    severity: float,
    location: int,
    width: int,
    load_factor: float,
    seed: int,
    cranfield_fault: str,
    cranfield_load: int,
    cranfield_repetition: int,
) -> tuple[RemoteTwinRun, str, str]:
    if analysis_source == "Cranfield 公开真实执行器":
        run = _api_client().diagnose_cranfield(
            {
                "asset_id": "CRANFIELD-EMA-01",
                "fault": (
                    "lack_of_lubrication"
                    if cranfield_fault == "LackLubrication2.mat"
                    else "backlash"
                ),
                "load_kg": cranfield_load,
                "repetition": cranfield_repetition,
            }
        )
        return run, "CRANFIELD-EMA-01", "真实机电执行器台架 · 非水阀"
    run = _api_client().diagnose_simulation(
        {
            "asset_id": "DEMO-QD-007",
            "fault_type": fault_type,
            "severity": severity,
            "location_pct": float(location),
            "width_pct": float(width),
            "load_factor": float(load_factor),
            "seed": int(seed),
        }
    )
    return run, "DEMO-QD-007", "数字孪生受控实验 · 非产品实测"


st.set_page_config(
    page_title="SmartValve Operations",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="auto",
)
st.markdown(
    """
    <style>
    :root {--bg:#07111f;--panel:#101d2d;--line:#22364b;--ink:#e8f0f8;--muted:#8ea3b7;}
    .stApp {background:radial-gradient(circle at 80% -10%,#142b46 0,#07111f 36%);color:var(--ink);}
    [data-testid="stHeader"] {background:rgba(7,17,31,.78);backdrop-filter:blur(12px);}
    [data-testid="stAppDeployButton"], [data-testid="stMainMenu"] {display:none!important;}
    [data-testid="stSidebar"] {background:#0a1524;border-right:1px solid var(--line);}
    [data-testid="stSidebar"] * {color:#d7e4f1;}
    [data-testid="stSidebar"] [data-baseweb="select"] > div {background:#102238!important;
      border-color:#31506c!important;box-shadow:none!important;}
    [data-testid="stSidebar"] [data-baseweb="select"] span,
    [data-testid="stSidebar"] [data-baseweb="select"] div {color:#eef6fc!important;
      -webkit-text-fill-color:#eef6fc!important;opacity:1!important;}
    [data-testid="stSidebar"] [data-baseweb="select"] svg {fill:#75dce6!important;color:#75dce6!important;}
    [data-testid="stSidebar"] [data-baseweb="select"]:focus-within > div {border-color:#31c7d7!important;
      box-shadow:0 0 0 1px #31c7d7,0 0 16px rgba(49,199,215,.12)!important;}
    div[data-baseweb="popover"] [role="listbox"] {background:#0d1c2d!important;
      border:1px solid #31506c!important;}
    div[data-baseweb="popover"] [role="option"] {background:#0d1c2d!important;color:#dcebf7!important;
      -webkit-text-fill-color:#dcebf7!important;}
    div[data-baseweb="popover"] [role="option"]:hover,
    div[data-baseweb="popover"] [aria-selected="true"] {background:#17334a!important;color:#75e6ee!important;
      -webkit-text-fill-color:#75e6ee!important;}
    .block-container {padding:1.1rem 2rem 3rem;max-width:1680px;}
    h1,h2,h3 {letter-spacing:-.025em;color:#f4f8fc!important;}
    p,li {color:#a9bacb;}
    .app-header {display:flex;align-items:center;justify-content:space-between;padding:.5rem 0 1.2rem;
      border-bottom:1px solid var(--line);margin-bottom:1.2rem;}
    .brand {display:flex;gap:.9rem;align-items:center;}.brand-mark {width:42px;height:42px;border:1px solid #31c7d7;
      color:#31c7d7;display:grid;place-items:center;transform:rotate(45deg);box-shadow:0 0 24px rgba(49,199,215,.15);}
    .brand-mark span {transform:rotate(-45deg);font-size:18px}.eyebrow {font-size:.68rem;letter-spacing:.18em;
      color:#6f8da8;font-weight:700}.brand h1 {font-size:1.32rem;margin:.12rem 0 0}.header-meta {text-align:right;
      font-size:.72rem;color:#7790a8}.live-dot {display:inline-block;width:7px;height:7px;background:#3ddc97;
      border-radius:50%;margin-right:.4rem;box-shadow:0 0 10px #3ddc97}
    .source-chip {display:inline-flex;padding:.28rem .58rem;border:1px solid #29415a;border-radius:4px;
      background:#0c1928;color:#9eb4c8;font-size:.68rem;font-weight:700;letter-spacing:.05em;margin-top:.3rem}
    [data-testid="stMetric"] {background:linear-gradient(145deg,#111f30,#0d1928);border:1px solid var(--line);
      border-radius:4px;padding:1rem 1rem .8rem;box-shadow:0 10px 28px rgba(0,0,0,.12);}
    [data-testid="stMetricLabel"] {color:#7f98ae;font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;}
    [data-testid="stMetricValue"] {color:#f2f7fb;font-weight:650;}
    [data-testid="stMetricDelta"] {font-size:.72rem;}
    .status-strip {display:grid;grid-template-columns:1fr 2fr 1fr;gap:1rem;align-items:center;padding:.9rem 1.1rem;
      border:1px solid var(--line);border-left:4px solid #3ddc97;background:#0d1928;margin:.4rem 0 1.2rem;border-radius:3px;}
    .status-strip.red {border-left-color:#ff5d6c}.status-strip.amber {border-left-color:#ffb547}
    .status-strip.blue {border-left-color:#4c8dff}.status-strip.green {border-left-color:#3ddc97}
    .status-strip small {display:block;color:#718aa1;font-size:.62rem;letter-spacing:.12em;margin-bottom:.16rem}
    .status-strip b {color:#eaf2f9;font-size:.85rem}.status-strip .signal {display:inline-block;width:8px;height:8px;
      border-radius:50%;background:#3ddc97;margin-right:.55rem}.status-strip.red .signal{background:#ff5d6c}
    .status-strip.amber .signal{background:#ffb547}.status-strip.blue .signal{background:#4c8dff}
    .section-head {display:flex;justify-content:space-between;align-items:flex-end;margin:1.1rem 0 .7rem}
    .section-head h2 {font-size:1.03rem;margin:0}.section-head span {font-size:.68rem;color:#7089a0;letter-spacing:.1em}
    .industrial-card {height:100%;padding:1rem;border:1px solid var(--line);background:#0d1928;border-radius:4px;}
    .industrial-card .grade {font-size:.64rem;color:#31c7d7;letter-spacing:.12em;font-weight:800}
    .industrial-card h3 {font-size:.96rem;margin:.5rem 0}.industrial-card p {font-size:.76rem;margin:.15rem 0}
    .pass {color:#3ddc97!important}.pending {color:#ffb547!important}.locked {color:#71869a!important}
    [data-testid="stDataFrame"] {border:1px solid var(--line);border-radius:3px;overflow:hidden;}
    [data-testid="stTabs"] button {color:#91a8bc;}[data-testid="stTabs"] button[aria-selected="true"] {color:#31c7d7;}
    .event {display:grid;grid-template-columns:72px 110px 1fr;gap:.8rem;padding:.65rem 0;border-bottom:1px solid #1d3043;
      font-size:.76rem}.event .time {color:#718aa1}.event .tag {font-weight:800;color:#ffb547}.event .body{color:#b9c8d6}
    .stDownloadButton button,.stButton button,.stLinkButton a {border-radius:3px;border-color:#31506c;background:#102238;color:#dcebf7;}
    div[data-testid="stAlert"] {border-radius:3px;background:#0d1c2d;border-color:#294158;}
    @media (max-width:900px){.status-strip{grid-template-columns:1fr}.header-meta{display:none}.block-container{padding:1rem}}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### ◆ SMARTVALVE")
    st.caption(f"CONDITION INTELLIGENCE / v{__version__}")
    page = st.radio(
        "工作区",
        ["资产总览", "单阀诊断", "管网影响", "三源验证", "系统与审计"],
        label_visibility="collapsed",
    )
    st.divider()
    analysis_source = st.selectbox(
        "当前数据源", ["仿真诊断实验室", "Cranfield 公开真实执行器"]
    )
    with st.form("diagnostic-execution"):
        if analysis_source == "仿真诊断实验室":
            fault_label = st.selectbox("故障场景", list(FAULT_LABELS), index=2)
            severity = st.slider("故障严重度", 0.0, 1.0, 0.75, 0.05)
            with st.expander("工况参数"):
                location = st.slider("故障中心开度 / %", 10, 90, 65, 1)
                width = st.slider("影响区间宽度 / %", 2, 20, 8, 1)
                load_factor = st.slider("外部负载系数", 0.7, 1.5, 1.0, 0.05)
                seed = st.number_input("随机种子", min_value=0, max_value=9999, value=7)
            cranfield_fault_label, cranfield_load, cranfield_repetition = (
                "润滑不足 · Stage 2",
                20,
                1,
            )
        else:
            cranfield_fault_label = st.selectbox(
                "真实故障工况", ["润滑不足 · Stage 2", "机械间隙 · Stage 2"]
            )
            cranfield_load = st.selectbox("台架负载 / kgf", [20, 40, -40])
            cranfield_repetition = st.slider("重复实验编号", 1, 10, 1)
            fault_label, severity, location, width, load_factor, seed = (
                "正常基线",
                0.0,
                65,
                8,
                1.0,
                7,
            )
        execute_diagnosis = st.form_submit_button(
            "执行并固化诊断", type="primary", width="stretch"
        )
        st.caption("只有点击执行才调用 API 并写入不可变审计链。")
    st.divider()
    try:
        sidebar_readiness = _runtime_status()
        engine_online = sidebar_readiness.get("status") == "ready"
    except ApiClientError:
        sidebar_readiness = {}
        engine_online = False
    if engine_online:
        st.markdown('<span class="live-dot"></span>诊断引擎在线', unsafe_allow_html=True)
        st.caption(f"规则模型 {MODEL_VERSION}")
        st.caption(str(sidebar_readiness.get("hydraulic_engine", "WNTR PDD")))
    else:
        st.error("诊断引擎不可用或未就绪")
        st.caption("请检查 API、数据库和 WNTR 就绪探针。")

cranfield_fault = (
    "LackLubrication2.mat"
    if analysis_source == "仿真诊断实验室" or cranfield_fault_label.startswith("润滑")
    else "Backlash2.mat"
)
cranfield_load_value = 20 if analysis_source == "仿真诊断实验室" else int(cranfield_load)
cranfield_repetition_value = 1 if analysis_source == "仿真诊断实验室" else int(cranfield_repetition)
execution_parameters = (
    analysis_source,
    FAULT_LABELS[fault_label],
    float(severity),
    int(location),
    int(width),
    float(load_factor),
    int(seed),
    cranfield_fault,
    cranfield_load_value,
    cranfield_repetition_value,
)
if execute_diagnosis:
    try:
        with st.spinner("正在验证数据、运行诊断并固化审计记录…"):
            st.session_state.active_diagnostic = _load_run(*execution_parameters)
            st.session_state.active_parameters = execution_parameters
    except ApiClientError as exc:
        st.error(f"诊断 API 不可用：{exc}")
        st.code("make demo\n# 或分别运行 make api 与 make dashboard", language="bash")
        st.stop()
if "active_diagnostic" not in st.session_state:
    st.markdown(
        f"""
        <div class="app-header">
          <div class="brand"><div class="brand-mark"><span>◆</span></div><div>
            <div class="eyebrow">OPERATIONS / CONTROLLED EXECUTION</div>
            <h1>SmartValve Condition Intelligence</h1></div></div>
          <div class="header-meta"><span class="live-dot"></span>PLATFORM READY · {datetime.now().strftime("%H:%M:%S")}
            <br><span class="source-chip">AWAITING OPERATOR</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="section-head"><h2>受控诊断工作台</h2><span>SELECT → EXECUTE → AUDIT</span></div>',
        unsafe_allow_html=True,
    )
    cards = st.columns(3)
    with cards[0]:
        st.markdown(
            '<div class="industrial-card"><div class="grade">01 · SELECT</div>'
            '<h3>选择证据来源</h3><p>仿真场景或公开真实执行器工况；两者边界不会混淆。</p></div>',
            unsafe_allow_html=True,
        )
    with cards[1]:
        st.markdown(
            '<div class="industrial-card"><div class="grade">02 · EXECUTE</div>'
            '<h3>执行完整计算链</h3><p>数据门禁、ValveDNA、WNTR 与证据解释在 API 内一次完成。</p></div>',
            unsafe_allow_html=True,
        )
    with cards[2]:
        st.markdown(
            '<div class="industrial-card"><div class="grade">03 · SEAL</div>'
            '<h3>固化不可变记录</h3><p>操作员、输入、完整载荷与结果进入 SHA-256 链式审计。</p></div>',
            unsafe_allow_html=True,
        )
    st.info("请在左侧确认参数，然后点击“执行并固化诊断”。本页面尚未调用诊断 API，也未写入审计库。")
    st.stop()
run, asset_id, source_context = st.session_state.active_diagnostic
parameters_pending = st.session_state.get("active_parameters") != execution_parameters
source_id = str(run.current_data["source"].iloc[0])

st.markdown(
    f"""
    <div class="app-header">
      <div class="brand"><div class="brand-mark"><span>◆</span></div><div>
        <div class="eyebrow">OPERATIONS / ASSET RELIABILITY</div>
        <h1>SmartValve Condition Intelligence</h1></div></div>
      <div class="header-meta"><span class="live-dot"></span>PLATFORM ONLINE · {datetime.now().strftime("%H:%M:%S")}
        <br><span class="source-chip">{_source_badge(source_id)}</span>
        <span class="source-chip">RUN {run.run_id[:8]}</span></div>
    </div>
    """,
    unsafe_allow_html=True,
)
if parameters_pending:
    st.info("侧栏参数尚未执行；当前仍显示上一条已固化诊断。点击“执行并固化诊断”后更新。")

if page == "资产总览":
    st.markdown(
        '<div class="section-head"><h2>资产健康总览</h2><span>FLEET / PRIORITY BY CONDITION × IMPACT</span></div>',
        unsafe_allow_html=True,
    )
    fleet = _fleet_frame(run)
    critical = int(fleet["状态"].isin(["FAILURE", "OUT OF SPEC"]).sum())
    maintenance = int(fleet["状态"].eq("MAINTENANCE").sum())
    metrics = st.columns(5)
    metrics[0].metric("演示资产", f"{len(fleet)}", "合成场景，非伟隆实物")
    metrics[1].metric("正常运行", f"{int(fleet['状态'].eq('NORMAL').sum())}", "稳定")
    metrics[2].metric("需维护", f"{maintenance}", "按状态排序")
    metrics[3].metric("严重状态", f"{critical}", "优先处理" if critical else "无")
    metrics[4].metric("证据源就绪", "3 / 4", "S0 + 2×S1；S2 待硬件")
    st.markdown(
        '<div class="section-head"><h2>实时系统态势</h2><span>DATA-DRIVEN FLOW / PRESSURE PROPAGATION</span></div>',
        unsafe_allow_html=True,
    )
    _network_twin_animation(run)
    left, right = st.columns([1.08, 0.92])
    with left:
        st.plotly_chart(_fleet_map(fleet), width="stretch", key="fleet-map")
    with right:
        st.markdown("#### 维护优先队列")
        priority = fleet.sort_values(["系统影响", "健康分"], ascending=[False, True])
        st.dataframe(
            priority,
            hide_index=True,
            width="stretch",
            column_config={
                "健康分": st.column_config.ProgressColumn(
                    "健康分", min_value=0, max_value=100, format="%.1f"
                ),
                "系统影响": st.column_config.ProgressColumn(
                    "系统影响", min_value=0, max_value=100, format="%.0f"
                ),
            },
        )
    st.markdown(
        '<div class="section-head"><h2>当前演示事件</h2><span>SYNTHETIC EVENT REPLAY</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="event"><span class="time">刚刚</span><span class="tag">DIAGNOSTIC</span><span class="body">{asset_id} · {run.diagnosis.primary_finding}</span></div>
        <div class="event"><span class="time">-08 min</span><span class="tag">NETWORK</span><span class="body">WNTR 影响计算完成 · 受影响节点 {", ".join(run.network.affected_nodes) or "无"}</span></div>
        <div class="event"><span class="time">-21 min</span><span class="tag pass">DATA QA</span><span class="body">数据契约通过 · 质量分 {run.current_quality.score:.1f} · SHA-256 已记录</span></div>
        """,
        unsafe_allow_html=True,
    )

elif page == "单阀诊断":
    st.markdown(
        f'<div class="section-head"><h2>{asset_id} · 单阀状态诊断</h2><span>{source_context.upper()}</span></div>',
        unsafe_allow_html=True,
    )
    _status_banner(run)
    metrics = st.columns(6)
    metrics[0].metric("健康指数", f"{run.diagnosis.health_score:.1f}", "/ 100")
    metrics[1].metric("签名相似度", f"{run.signature.similarity_pct:.1f}%")
    metrics[2].metric(
        "规则证据强度", f"{run.diagnosis.confidence * 100:.0f}%", "非统计校准概率"
    )
    metrics[3].metric("可用行程", f"{run.diagnosis.available_travel_pct:.1f}%")
    metrics[4].metric("数据质量", f"{run.current_quality.score:.1f}", run.current_quality.status)
    metrics[5].metric("采样率", f"{run.current_quality.sampling_hz:.1f} Hz")
    replay_label = (
        "SETPOINT × POSITION × CURRENT / MEASURED ACTUATOR REPLAY"
        if source_id == "cranfield_real_actuator"
        else "POSITION × CURRENT × FLOW / 12-SECOND REPLAY"
    )
    st.markdown(
        f'<div class="section-head"><h2>动态内部透视</h2><span>{replay_label}</span></div>',
        unsafe_allow_html=True,
    )
    _valve_twin_animation(run, asset_id)
    if source_id == "cranfield_real_actuator":
        st.caption(
            "丝杠执行器位移、设定值与电流均由 Cranfield 实测序列逐点驱动；"
            "不渲染水流，也不声称这是水阀数据。"
        )
    else:
        st.caption(
            "阀板角度、电流环与仿真流量均由当前 S0 数据逐点驱动；动画压缩为 12 秒循环回放。"
        )
    with st.expander("展开 ValveDNA 工程证据曲线", expanded=False):
        left, right = st.columns(2)
        with left:
            st.plotly_chart(_signature_figure(run), width="stretch", key="signature")
        with right:
            st.plotly_chart(_time_series_figure(run), width="stretch", key="response")
    left, right = st.columns([1.05, 0.95])
    with left:
        st.markdown("#### 诊断证据链")
        evidence = pd.DataFrame(
            [{"证据变量": key, "当前值": value} for key, value in run.diagnosis.evidence.items()]
        )
        st.dataframe(evidence, hide_index=True, width="stretch")
    with right:
        st.markdown("#### 建议工作单")
        st.info(run.diagnosis.recommendation)
        start, end = run.diagnosis.abnormal_start_pct, run.diagnosis.abnormal_end_pct
        interval = f"{start:.0f}–{end:.0f}%" if start is not None and end is not None else "未定位"
        work_order = pd.DataFrame(
            [
                ("资产", asset_id),
                ("优先级", _status_style(run.diagnosis.ne107_status)[0]),
                ("决策状态", run.diagnosis.decision_state),
                ("异常区间", interval),
                ("证据等级", _source_badge(source_id)),
                ("模型版本", run.model_version),
            ],
            columns=["字段", "值"],
        )
        st.dataframe(work_order, hide_index=True, width="stretch")
        report = _report_markdown(run, asset_id)
        st.download_button(
            "导出诊断报告",
            data=report,
            file_name=f"{asset_id}_condition_report.md",
            mime="text/markdown",
            width="stretch",
        )
        st.download_button(
            "导出机器可读 JSON",
            data=json.dumps(
                {
                    "asset_id": asset_id,
                    "source": source_id,
                    "diagnosis": run.diagnosis.to_dict(),
                    "network": run.network.to_dict(),
                    "quality": run.current_quality.to_dict(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file_name=f"{asset_id}_result.json",
            mime="application/json",
            width="stretch",
        )
        st.download_button(
            "导出正式 PDF 报告",
            data=_load_diagnostic_pdf(run.run_id),
            file_name=f"{asset_id}_condition_report.pdf",
            mime="application/pdf",
            width="stretch",
        )

elif page == "管网影响":
    st.markdown(
        '<div class="section-head"><h2>阀门—管网影响孪生</h2><span>ASSET CONDITION → SERVICE CONSEQUENCE</span></div>',
        unsafe_allow_html=True,
    )
    if source_id != "simulation":
        st.warning(
            "当前外部执行器数据没有对应水阀 Kv/Cv，以下水力层仅展示接口，不作为真实水力验证。"
        )
    affected = "、".join(run.network.affected_nodes) or "无"
    metrics = st.columns(5)
    metrics[0].metric("系统影响指数", f"{run.network.impact_score:.1f}", "/ 100")
    metrics[1].metric("受影响节点", affected)
    metrics[2].metric("等效损失系数", f"{run.network.equivalent_loss_coefficient:.1f}")
    metrics[3].metric("最低节点压力", f"{min(run.network.fault_pressure_m.values()):.1f} m")
    metrics[4].metric("服务压力阈值", f"{run.network.service_pressure_threshold_m:.1f} m")
    _network_twin_animation(run)
    st.caption(
        "水粒子速度按各管段 WNTR 流量缩放；节点颜色和红色冲击波由服务压力阈值判定。"
    )
    with st.expander("展开水力工程证据图", expanded=False):
        left, right = st.columns([1.04, 0.96])
        with left:
            st.plotly_chart(_network_figure(run), width="stretch", key="network")
        with right:
            st.plotly_chart(_pressure_figure(run), width="stretch", key="pressure")
    flow_frame = pd.DataFrame(
        {
            "管段": list(run.network.baseline_flow_lps),
            "基线流量 / L·s⁻¹": list(run.network.baseline_flow_lps.values()),
            "当前流量 / L·s⁻¹": list(run.network.fault_flow_lps.values()),
        }
    )
    flow_frame["变化 / %"] = (
        (flow_frame["当前流量 / L·s⁻¹"] / flow_frame["基线流量 / L·s⁻¹"] - 1.0) * 100.0
    ).round(1)
    st.dataframe(flow_frame, hide_index=True, width="stretch")
    st.caption(
        f"计算引擎：{run.network.engine}。可用行程→等效损失系数为可替换映射，"
        "在获得企业 Kv/Cv 或台架曲线前不标记为产品校准。"
    )

elif page == "三源验证":
    st.markdown(
        '<div class="section-head"><h2>证据阶梯与三源验证</h2><span>SIMULATION → PUBLIC RIG → OWN RIG → ENTERPRISE</span></div>',
        unsafe_allow_html=True,
    )
    card_columns = st.columns(4)
    cards = [
        (
            "S0 · SIMULATION",
            "可复现故障注入",
            "PASS",
            "受控生成摩擦、卡涩、阻塞和传感器漂移",
            "pass",
        ),
        (
            "S1 · PUBLIC RIG",
            "公开真实台架",
            "DATA VERIFIED",
            "Cranfield 迁移 + SKAB 异常检测；机械根因分类仍有限",
            "pass",
        ),
        (
            "S2 · OWN RIG",
            "200 元自有样机",
            "接口就绪 / 硬件待建",
            "统一 CSV 契约已完成，硬件尚未采购",
            "pending",
        ),
        (
            "S3 · ENTERPRISE CANDIDATE",
            "伟隆产品验证",
            "LOCKED",
            "需要型号参数、协议和现场/出厂数据",
            "locked",
        ),
    ]
    for column, (grade, title, status_text, detail, tone) in zip(card_columns, cards, strict=True):
        with column:
            st.markdown(
                f'<div class="industrial-card"><div class="grade">{grade}</div><h3>{title}</h3>'
                f'<p class="{tone}"><b>{status_text}</b></p><p>{detail}</p></div>',
                unsafe_allow_html=True,
            )

    st.markdown(
        '<div class="section-head"><h2>3000条分组实验矩阵</h2><span>UNSEEN LOAD HOLDOUT / NO ROW-LEVEL LEAKAGE</span></div>',
        unsafe_allow_html=True,
    )
    benchmark = _load_benchmark("full")
    challenge = _load_benchmark("challenge")
    challenge_result = challenge["holdout"]
    matrix = benchmark["matrix"]
    metrics = st.columns(6)
    metrics[0].metric(
        "参数化实验",
        f"{matrix['total_runs']:,}",
        f"{matrix['unique_observable_runs']:,} 条唯一可观测轨迹",
    )
    metrics[1].metric("锁定挑战集", f"{challenge['matrix']['total_runs']:,}", "独立负载/种子")
    metrics[2].metric(
        "挑战集宏 F1", f"{challenge_result['macro_f1_including_rejection_as_error']:.3f}"
    )
    metrics[3].metric(
        "挑战集误报率", f"{challenge_result['false_positive_rate_normal'] * 100:.1f}%"
    )
    metrics[4].metric(
        "越界电压拒识",
        f"{challenge_result['out_of_spec_voltage_rejection_recall']:.3f}",
        "非通用 OOD",
    )
    metrics[5].metric("挑战集 P95", f"{challenge_result['latency_ms']['p95']:.1f} ms")
    class_frame = pd.DataFrame.from_dict(challenge_result["per_class"], orient="index")
    class_frame.index.name = "故障类别"
    class_frame = class_frame.reset_index().rename(
        columns={"precision": "Precision", "recall": "Recall", "f1": "F1", "support": "样本"}
    )
    st.dataframe(class_frame, hide_index=True, width="stretch")
    st.caption(
        "3000组参数中有2100条唯一可观测轨迹；重复来自严重度为0时不同故障参数产生同一正常信号，"
        "不再把它们表述为独立样本。锁定挑战集在0.3规则冻结后创建，使用不同负载点与随机种子。"
        "两者都只属于S0仿真，不得解释为伟隆产品或现场准确率。"
    )

    st.markdown(
        '<div class="section-head"><h2>Cranfield · 真实执行器签名迁移验证</h2><span>CC BY 4.0 / 25 HZ / 2,000 SAMPLES</span></div>',
        unsafe_allow_html=True,
    )
    source_payload = _source_status()
    artifacts = source_payload["artifacts"]
    availability = {item["filename"]: item["available"] for item in artifacts}
    if availability.get("Normal.mat") and availability.get("LackLubrication2.mat"):
        grouped_validation = _load_cranfield_validation()
        grouped_results = grouped_validation["results"]
        grouped_dataset = grouped_validation["dataset"]
        grouped_folds = pd.DataFrame(grouped_results["folds"])
        weakest_fold = grouped_folds.loc[grouped_folds["accuracy"].idxmin()]
        metrics = st.columns(5)
        metrics[0].metric("全部真实试验", f"{grouped_dataset['trials']}", "非单一样本")
        metrics[1].metric(
            "未见负载折", f"{grouped_validation['protocol']['folds']}", "按负载完整隔离"
        )
        metrics[2].metric("开发交叉验证准确率", f"{grouped_results['accuracy'] * 100:.1f}%")
        metrics[3].metric("宏平均 F1", f"{grouped_results['macro_f1']:.3f}")
        metrics[4].metric(
            "最弱工况",
            f"{weakest_fold['accuracy'] * 100:.1f}%",
            f"{weakest_fold['motion']} / {int(weakest_fold['held_out_load_kg'])} kgf",
            delta_color="inverse",
        )
        st.warning(
            "公开数据的薄弱点也完整展示：梯形运动 -40 kgf 未见负载折仅 33.3%。"
            "因此 87.2% 是开发交叉验证结果，不是可部署模型精度，更不是伟隆产品准确率。"
        )
        with st.expander("展开 180 组分组验证明细", expanded=False):
            per_class = pd.DataFrame.from_dict(grouped_results["per_class"], orient="index")
            per_class.index.name = "真实类别"
            st.dataframe(
                per_class.reset_index().rename(
                    columns={
                        "precision": "Precision",
                        "recall": "Recall",
                        "f1-score": "F1",
                        "support": "试验数",
                    }
                ),
                hide_index=True,
                width="stretch",
            )
            fold_figure = go.Figure(
                go.Bar(
                    x=grouped_folds["accuracy"] * 100,
                    y=(
                        grouped_folds["motion"].str.upper()
                        + " / "
                        + grouped_folds["held_out_load_kg"].astype(str)
                        + " kgf"
                    ),
                    orientation="h",
                    marker_color=np.where(
                        grouped_folds["accuracy"] >= 0.8, COLORS["green"], COLORS["red"]
                    ),
                    text=(grouped_folds["accuracy"] * 100).map(lambda value: f"{value:.1f}%"),
                    textposition="auto",
                    hovertemplate="未见负载准确率 %{x:.1f}%<extra></extra>",
                )
            )
            fold_figure.update_xaxes(title="准确率 / %", range=[0, 105])
            fold_figure.update_yaxes(title="完整留出工况")
            st.plotly_chart(_plot_style(fold_figure, height=330), width="stretch")
            st.caption(
                "每折只用同一运动形式下另外两个负载训练；测试负载的带标签试验完全不参与拟合。"
                "同工况健康基线作为诊断输入，不等于把测试标签泄漏给模型。"
            )

        st.markdown("#### 单次实测证据回放")
        real_run = _load_public_cranfield()
        metrics = st.columns(5)
        metrics[0].metric("实测样本", f"{real_run.current_quality.sample_count:,}")
        metrics[1].metric("采样率", f"{real_run.current_quality.sampling_hz:.0f} Hz")
        metrics[2].metric(
            "运动电流比", f"{real_run.diagnosis.evidence['moving_current_ratio']:.3f}"
        )
        metrics[3].metric("签名相似度", f"{real_run.signature.similarity_pct:.1f}%")
        metrics[4].metric("透明规则结论", real_run.diagnosis.primary_finding)
        _valve_twin_animation(real_run, "CRANFIELD-EMA-01")
        with st.expander("展开 Cranfield 原始工程曲线", expanded=False):
            left, right = st.columns(2)
            with left:
                st.plotly_chart(_signature_figure(real_run), width="stretch", key="cran-signature")
            with right:
                st.plotly_chart(_time_series_figure(real_run), width="stretch", key="cran-response")
        st.caption(
            "来源：Cranfield Electromechanical Actuator Dataset。真实球丝杠机电执行器，故障为人工逐级植入；"
            "可验证电流—位置迁移方法，但不能冒充水阀或伟隆产品数据。"
        )
    else:
        st.warning("Cranfield 数据未同步。运行 `make data` 后启用真实台架验证。")

    st.markdown(
        '<div class="section-head"><h2>SKAB · 真实水循环异常验证</h2><span>PHYSICAL WATER LOOP / VALVE 1</span></div>',
        unsafe_allow_html=True,
    )
    if availability.get("skab_valve1_1.csv"):
        skab = _load_skab_validation()
        skab_figure = _skab_figure(skab)
        metrics = st.columns(5)
        metrics[0].metric("实测样本", f"{skab.total_samples:,}")
        metrics[1].metric("独立评测点", f"{skab.evaluation_samples:,}")
        metrics[2].metric("Precision", f"{skab.precision:.3f}")
        metrics[3].metric("Recall", f"{skab.recall:.3f}")
        metrics[4].metric("F1", f"{skab.f1:.3f}")
        st.plotly_chart(skab_figure, width="stretch", key="skab")
        st.caption(
            "来源：SKAB Real Water Circulation Testbed。指标来自固定前 400 点训练的透明鲁棒距离基线，"
            "没有用标签调阈值；它验证水循环异常检测，不证明机械根因分类。"
        )
    else:
        st.warning("SKAB 数据未同步。运行 `make data` 后启用真实水循环验证。")

    st.markdown(
        '<div class="section-head"><h2>自有样机 / 企业 CSV 接口</h2><span>CANONICAL FULL-STROKE CONTRACT V1</span></div>',
        unsafe_allow_html=True,
    )
    baseline_upload = st.file_uploader("上传健康基线 CSV", type="csv", key="baseline-upload")
    current_upload = st.file_uploader("上传当前测试 CSV", type="csv", key="current-upload")
    if baseline_upload is not None and current_upload is not None:
        try:
            uploaded_run = _api_client().diagnose_csv(
                asset_id="DESKTOP-RIG-UPLOAD",
                source="desktop_rig",
                baseline=baseline_upload.getvalue(),
                current=current_upload.getvalue(),
            )
            st.success(
                f"数据契约通过：基线 {uploaded_run.baseline_quality.score:.1f} / "
                f"当前 {uploaded_run.current_quality.score:.1f} · RUN {uploaded_run.run_id[:8]}"
            )
            st.plotly_chart(_signature_figure(uploaded_run), width="stretch", key="uploaded")
        except ApiClientError as exc:
            st.error(f"拒绝导入：{exc}")

elif page == "系统与审计":
    st.markdown(
        '<div class="section-head"><h2>工程运行状态</h2><span>API / DATA CONTRACT / AUDIT / MODEL BOUNDARY</span></div>',
        unsafe_allow_html=True,
    )
    try:
        readiness = _runtime_status()
        audit_verification = _audit_status()
    except ApiClientError as exc:
        st.error(f"运行状态验证失败：{exc}")
        readiness = {"status": "degraded", "database": False, "hydraulic_ready": False}
        audit_verification = {"valid": False, "records": 0}
    metrics = st.columns(6)
    metrics[0].metric("API 版本", "v1", f"软件 {__version__}")
    metrics[1].metric(
        "存储", "READY" if readiness.get("database") else "DEGRADED", "SQLite WAL"
    )
    metrics[2].metric(
        "水力引擎", "READY" if readiness.get("hydraulic_ready") else "DEGRADED", "WNTR PDD"
    )
    metrics[3].metric(
        "审计哈希链", "OK" if audit_verification.get("valid") else "FAILED",
        f"{audit_verification.get('checked_records', 0)} 条全链校验",
    )
    metrics[4].metric("模型版本", MODEL_VERSION.removeprefix("valvedna-rules-"), "规则可审计")
    metrics[5].metric("证据最高等级", "S1", "公开真实台架")
    left, right = st.columns([1.08, 0.92])
    with left:
        st.markdown("#### 服务接口")
        endpoints = pd.DataFrame(
            [
                ("GET", "/health/live", "进程存活探针", "公开"),
                ("GET", "/health/ready", "数据库与水力引擎就绪", "公开"),
                ("GET", "/metrics", "Prometheus 文本指标", "公开"),
                ("GET", "/v1/sources", "数据源与证据等级", "正式环境必需 API Key"),
                ("POST", "/v1/diagnostics/simulation", "版本化诊断请求", "正式环境必需 API Key"),
                ("POST", "/v1/diagnostics/cranfield", "公开真实执行器诊断", "正式环境必需 API Key"),
                ("POST", "/v1/diagnostics/csv", "样机/企业 CSV 双文件诊断", "正式环境必需 API Key"),
                ("GET", "/v1/validation/skab", "真实水循环独立评测", "正式环境必需 API Key"),
                ("GET", "/v1/validation/benchmark", "3000条分组实验指标", "正式环境必需 API Key"),
                (
                    "GET",
                    "/v1/validation/cranfield",
                    "180组真实执行器未见负载验证",
                    "正式环境必需 API Key",
                ),
                ("GET", "/v1/runs", "不可变运行审计索引", "正式环境必需 API Key"),
                ("GET", "/v1/audit/verify", "校验完整 SHA-256 哈希链", "正式环境必需 API Key"),
                (
                    "GET",
                    "/v1/runs/{id}/report.pdf",
                    "审计记录正式报告",
                    "正式环境必需 API Key",
                ),
            ],
            columns=["方法", "路径", "用途", "访问控制"],
        )
        st.dataframe(endpoints, hide_index=True, width="stretch")
        st.code("make api\n# OpenAPI: http://localhost:8000/docs", language="bash")
    with right:
        st.markdown("#### 最近诊断审计")
        try:
            records = _api_client().list_runs(limit=10)
            if records:
                audit = pd.DataFrame(records)
                audit["资产显示编号"] = audit["asset_id"].where(
                    ~audit["asset_id"].str.startswith("WL-"),
                    "LEGACY-DEMO-" + audit["asset_id"].str.removeprefix("WL-"),
                )
                audit["data_sha256"] = audit["data_sha256"].str[:12] + "…"
                st.dataframe(
                    audit[
                        [
                            "created_at",
                            "资产显示编号",
                            "source",
                            "status",
                            "health_score",
                            "evidence_grade",
                            "data_sha256",
                        ]
                    ],
                    hide_index=True,
                    width="stretch",
                )
            else:
                st.info("API 尚未写入诊断记录。调用 POST /v1/diagnostics/simulation 后显示。")
        except ApiClientError as exc:
            st.error(f"审计库不可用：{exc}")
    st.markdown(
        '<div class="section-head"><h2>数据来源与完整性</h2><span>PROVENANCE / LICENSE / LOCAL CACHE</span></div>',
        unsafe_allow_html=True,
    )
    artifact_frame = pd.DataFrame(_source_status()["artifacts"])
    artifact_frame["状态"] = np.select(
        [artifact_frame["integrity_verified"], artifact_frame["available"]],
        ["SHA-256 VERIFIED", "UNVERIFIED"],
        default="NOT SYNCED",
    )
    st.dataframe(
        artifact_frame[
            ["source_id", "filename", "bytes", "license_name", "状态", "citation_url"]
        ],
        hide_index=True,
        width="stretch",
        column_config={"citation_url": st.column_config.LinkColumn("来源")},
    )
    st.markdown("#### 明确边界")
    st.warning(
        "当前最高证据等级为 S1：公开真实台架。尚未完成伟隆产品校准、真实 Kv/Cv 映射、"
        "长期退化/RUL、安全认证或现场高可用验收，因此定位为可部署工业工程 PoC，而非已投产产品。"
    )
