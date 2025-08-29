#!/usr/bin/env python3
# combine_svgs_side_by_side.py
import argparse, re, copy, xml.etree.ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace('', SVG_NS)
U = {"px":1.0, "pt":96/72, "pc":16, "mm":96/25.4, "cm":96/2.54, "in":96}

def parse_len(s):
    if not s: return None
    s=s.strip()
    m=re.match(r'^([0-9]*\.?[0-9]+)([a-z%]*)$', s)
    if not m: return None
    val=float(m.group(1)); unit=m.group(2) or "px"
    if unit=="%": return None
    return val*U.get(unit,1.0)

def dims(root):
    w=parse_len(root.get("width"))
    h=parse_len(root.get("height"))
    vb=root.get("viewBox")
    if vb:
        v=list(map(float, re.split(r'[ ,]+', vb.strip())))
        minx,miny,vbw,vbh=v
        if w is None and h is None:
            w, h = vbw, vbh
    else:
        minx=miny=0.0
        vbw, vbh = (w or 0.0), (h or 0.0)
    return w, h, (minx, miny, vbw, vbh)

def svg(tag, **attrs):
    return ET.Element(f'{{{SVG_NS}}}{tag}', {k:str(v) for k,v in attrs.items()})

def load(path):
    tree=ET.parse(path); root=tree.getroot()
    return tree, root

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("left"); ap.add_argument("right"); ap.add_argument("out")
    ap.add_argument("--gap", type=float, default=0.0, help="gap between images in px")
    ap.add_argument("--match-height", action="store_true",
                    help="scale the shorter one up so both heights match")
    # NEW: optional EPS export path
    ap.add_argument("--eps", metavar="OUT_EPS",
                    help="also export an EPS to this path (requires CairoSVG or Inkscape)")
    args = ap.parse_args()

    _, L = load(args.left); lw, lh, (lminx,lminy,lvbw,lvbh) = dims(L)
    _, R = load(args.right); rw, rh, (rminx,rminy,rvbw,rvbh) = dims(R)

    if lw is None or lh is None or rw is None or rh is None:
        raise SystemExit("Both SVGs must have width/height or a viewBox.")

    # Optionally scale so heights match
    if args.match_height:
        target = max(lh, rh)
        if lh != target:
            scale = target/lh; lw *= scale; lh = target
        if rh != target:
            scale = target/rh; rw *= scale; rh = target

    total_w = lw + args.gap + rw
    total_h = max(lh, rh)

    OUT = svg("svg", width=f"{total_w}px", height=f"{total_h}px",
              viewBox=f"0 0 {total_w} {total_h}")

    # Left
    left_n = svg("svg", x="0", y="0", width=f"{lw}", height=f"{lh}",
                 viewBox=L.get("viewBox") or f"0 0 {lvbw or lw} {lvbh or lh}")
    for c in list(L):
        left_n.append(copy.deepcopy(c))
    OUT.append(left_n)

    # Right
    right_n = svg("svg", x=f"{lw + args.gap}", y="0", width=f"{rw}", height=f"{rh}",
                  viewBox=R.get("viewBox") or f"0 0 {rvbw or rw} {rvbh or rh}")
    for c in list(R):
        right_n.append(copy.deepcopy(c))
    OUT.append(right_n)

    ET.ElementTree(OUT).write(args.out, encoding="utf-8", xml_declaration=True)

    # EPS export (keeps vectors)
    if args.eps:
        svg_bytes = ET.tostring(OUT, encoding="utf-8", xml_declaration=True)
        # Try Python API first
        try:
            import cairosvg  # pip install cairosvg
            # CairoSVG supports EPS export since v2.5.0
            if hasattr(cairosvg, "svg2eps"):
                cairosvg.svg2eps(bytestring=svg_bytes, write_to=args.eps)
            else:
                # Older versions: use CLI if available
                _tmp = None
                if shutil.which("cairosvg"):
                    _tmp = tempfile.NamedTemporaryFile(suffix=".svg", delete=False)
                    _tmp.write(svg_bytes); _tmp.flush(); _tmp.close()
                    subprocess.run(["cairosvg", "-f", "eps", _tmp.name, "-o", args.eps],
                                   check=True)
                elif shutil.which("inkscape"):
                    _tmp = tempfile.NamedTemporaryFile(suffix=".svg", delete=False)
                    _tmp.write(svg_bytes); _tmp.flush(); _tmp.close()
                    subprocess.run([
                        "inkscape", _tmp.name,
                        "--export-type=eps",
                        f"--export-filename={args.eps}",
                        "--export-text-to-path"  # safer fonts in EPS
                    ], check=True)
                else:
                    raise RuntimeError("Need CairoSVG CLI or Inkscape for EPS export.")
        finally:
            if ' _tmp' in locals() and _tmp and os.path.exists(_tmp.name):
                os.unlink(_tmp.name)

if __name__ == "__main__":
    main()
