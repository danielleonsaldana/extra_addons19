/** @odoo-module **/

import { Component, onWillStart, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

const MIN_ZOOM = 1;
const MAX_ZOOM = 5;

function uid() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
}

function clamp(v, a, b) {
    return Math.min(Math.max(v, a), b);
}

/**
 * Geometría de una marca en coordenadas reales de la imagen (px).
 * Se usa igual para dibujar en pantalla (SVG) y para generar la imagen del reporte (canvas).
 */
export function markerGeometry(m, W, H) {
    const s = Math.max(W, H) / 48; // unidad base: escala con el tamaño del plano
    const tip = { x: m.x * W, y: m.y * H };
    const lab = { x: m.lx * W, y: m.ly * H };
    const r = s * 1.25; // radio de la etiqueta
    let dx = tip.x - lab.x;
    let dy = tip.y - lab.y;
    const len = Math.hypot(dx, dy) || 1;
    dx /= len;
    dy /= len;
    const start = { x: lab.x + dx * r, y: lab.y + dy * r };
    const head = s * 0.9;
    const base = { x: tip.x - dx * head, y: tip.y - dy * head };
    const nx = -dy;
    const ny = dx;
    const arrow = [
        [tip.x, tip.y],
        [base.x + nx * head * 0.45, base.y + ny * head * 0.45],
        [base.x - nx * head * 0.45, base.y - ny * head * 0.45],
    ];
    return {
        s,
        tip,
        lab,
        r,
        line: { x1: start.x, y1: start.y, x2: base.x, y2: base.y },
        showLine: len > r + head * 0.5,
        arrow,
        arrowPoints: arrow.map((p) => p.join(",")).join(" "),
        fontSize: s * 1.05,
        stroke: s * 0.2,
    };
}

export class VtJointMarker extends Component {
    static template = "mx_soldic_visual_inspection.VtJointMarker";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.actionService = useService("action");
        this.svgRef = useRef("svg");
        this.scrollRef = useRef("scroll");
        this.taskId =
            this.props.action?.params?.task_id || this.props.action?.context?.active_id;
        this.state = useState({
            loading: true,
            images: [],
            current: 0,
            zoom: 1,
            selected: null,
            dirty: false,
            saving: false,
            title: "",
        });
        this.history = [];
        this.drag = null;
        this.suppressClick = false;
        onWillStart(async () => {
            const data = await this.orm.call("project.task", "vt_get_marker_data", [[this.taskId]]);
            this.state.title = data.title;
            this.state.images = data.images.map((img) => ({
                ...img,
                markers: (img.markers || []).map((m) => ({ ...m })),
                w: 0,
                h: 0,
            }));
            this.state.loading = false;
        });
    }

    // ------------------------------------------------------------------ getters
    get image() {
        return this.state.images[this.state.current];
    }
    get totalJoints() {
        return this.state.images.reduce((acc, img) => acc + img.markers.length, 0);
    }
    get offset() {
        let n = 0;
        for (let i = 0; i < this.state.current; i++) {
            n += this.state.images[i].markers.length;
        }
        return n;
    }
    get viewMarkers() {
        const img = this.image;
        if (!img || !img.w) {
            return [];
        }
        const off = this.offset;
        return img.markers.map((m, i) => ({
            uid: m.uid,
            label: "J" + (off + i + 1),
            selected: this.state.selected === m.uid,
            g: markerGeometry(m, img.w, img.h),
        }));
    }
    get innerStyle() {
        return `width: ${this.state.zoom * 100}%;`;
    }

    // ------------------------------------------------------------------ helpers
    snapshot() {
        this.history.push(JSON.stringify(this.state.images.map((i) => i.markers)));
        if (this.history.length > 100) {
            this.history.shift();
        }
        this.state.dirty = true;
    }
    pointFromEvent(ev) {
        const rect = this.svgRef.el.getBoundingClientRect();
        return {
            x: clamp((ev.clientX - rect.left) / rect.width, 0, 1),
            y: clamp((ev.clientY - rect.top) / rect.height, 0, 1),
        };
    }
    findMarker(markerUid) {
        return this.image.markers.find((m) => m.uid === markerUid);
    }

    // ------------------------------------------------------------------ handlers
    onImageLoad(ev) {
        const img = this.image;
        img.w = ev.target.naturalWidth;
        img.h = ev.target.naturalHeight;
    }
    selectImage(idx) {
        this.state.current = idx;
        this.state.selected = null;
        this.state.zoom = 1;
    }
    onCanvasClick(ev) {
        if (this.suppressClick || !this.image.w) {
            return;
        }
        if (this.state.selected) {
            // primer toque fuera de una marca solo quita la selección
            this.state.selected = null;
            return;
        }
        const p = this.pointFromEvent(ev);
        const img = this.image;
        // etiqueta arriba-izquierda (o abajo si no cabe), misma distancia en px en ambos ejes
        const off = 0.07;
        const offY = (off * img.w) / img.h;
        let lx = p.x - off;
        let ly = p.y - offY;
        if (lx < 0.03) {
            lx = p.x + off;
        }
        if (ly < 0.03) {
            ly = p.y + offY;
        }
        this.snapshot();
        img.markers.push({ uid: uid(), x: p.x, y: p.y, lx: clamp(lx, 0.02, 0.98), ly: clamp(ly, 0.02, 0.98) });
    }
    onHandleTouchStart(ev) {
        // evita que el navegador desplace la pantalla mientras se arrastra
        ev.preventDefault();
    }
    onHandlePointerDown(ev, markerUid, kind) {
        ev.stopPropagation();
        const m = this.findMarker(markerUid);
        if (!m) {
            return;
        }
        this.drag = {
            uid: markerUid,
            kind,
            startX: ev.clientX,
            startY: ev.clientY,
            moved: false,
            orig: { ...m },
        };
        const move = (e) => this.onDragMove(e);
        const up = (e) => {
            window.removeEventListener("pointermove", move);
            window.removeEventListener("pointerup", up);
            window.removeEventListener("pointercancel", up);
            this.onDragEnd(e);
        };
        window.addEventListener("pointermove", move);
        window.addEventListener("pointerup", up);
        window.addEventListener("pointercancel", up);
    }
    onDragMove(ev) {
        const d = this.drag;
        if (!d) {
            return;
        }
        if (!d.moved && Math.hypot(ev.clientX - d.startX, ev.clientY - d.startY) < 6) {
            return;
        }
        if (!d.moved) {
            d.moved = true;
            this.snapshot();
        }
        const m = this.findMarker(d.uid);
        const p = this.pointFromEvent(ev);
        if (d.kind === "tip") {
            m.x = p.x;
            m.y = p.y;
        } else {
            m.lx = p.x;
            m.ly = p.y;
        }
    }
    onDragEnd() {
        const d = this.drag;
        this.drag = null;
        if (!d) {
            return;
        }
        if (!d.moved && d.kind === "label") {
            this.state.selected = this.state.selected === d.uid ? null : d.uid;
        }
        // el navegador dispara un click después del pointerup: no debe crear otra marca
        this.suppressClick = true;
        setTimeout(() => (this.suppressClick = false), 350);
    }
    zoomIn() {
        this.setZoom(this.state.zoom * 1.5);
    }
    zoomOut() {
        this.setZoom(this.state.zoom / 1.5);
    }
    setZoom(z) {
        const el = this.scrollRef.el;
        const ratio = clamp(z, MIN_ZOOM, MAX_ZOOM) / this.state.zoom;
        const cx = el.scrollLeft + el.clientWidth / 2;
        const cy = el.scrollTop + el.clientHeight / 2;
        this.state.zoom = clamp(z, MIN_ZOOM, MAX_ZOOM);
        requestAnimationFrame(() => {
            el.scrollLeft = cx * ratio - el.clientWidth / 2;
            el.scrollTop = cy * ratio - el.clientHeight / 2;
        });
    }
    undo() {
        const prev = this.history.pop();
        if (!prev) {
            return;
        }
        const arr = JSON.parse(prev);
        this.state.images.forEach((img, i) => (img.markers = arr[i] || []));
        this.state.selected = null;
        this.state.dirty = true;
    }
    deleteSelected() {
        if (!this.state.selected) {
            return;
        }
        this.snapshot();
        const img = this.image;
        img.markers = img.markers.filter((m) => m.uid !== this.state.selected);
        this.state.selected = null;
    }
    clearView() {
        if (!this.image.markers.length) {
            return;
        }
        this.dialog.add(ConfirmationDialog, {
            title: "Borrar marcas",
            body: `¿Borrar las ${this.image.markers.length} juntas marcadas en "${this.image.name}"?`,
            confirmLabel: "Borrar",
            confirm: () => {
                this.snapshot();
                this.image.markers = [];
                this.state.selected = null;
            },
            cancel: () => {},
        });
    }

    // ------------------------------------------------------------------ guardar
    loadImage(url) {
        return new Promise((resolve, reject) => {
            const im = new Image();
            im.onload = () => resolve(im);
            im.onerror = reject;
            im.src = url;
        });
    }
    async renderAnnotated(img, offset) {
        const im = await this.loadImage(img.url);
        const W = im.naturalWidth;
        const H = im.naturalHeight;
        const canvas = document.createElement("canvas");
        canvas.width = W;
        canvas.height = H;
        const ctx = canvas.getContext("2d");
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, W, H);
        ctx.drawImage(im, 0, 0, W, H);
        img.markers.forEach((m, i) => {
            const g = markerGeometry(m, W, H);
            ctx.strokeStyle = "#1f5fd6";
            ctx.fillStyle = "#1f5fd6";
            ctx.lineWidth = g.stroke;
            ctx.lineCap = "round";
            if (g.showLine) {
                ctx.beginPath();
                ctx.moveTo(g.line.x1, g.line.y1);
                ctx.lineTo(g.line.x2, g.line.y2);
                ctx.stroke();
            }
            ctx.beginPath();
            ctx.moveTo(...g.arrow[0]);
            ctx.lineTo(...g.arrow[1]);
            ctx.lineTo(...g.arrow[2]);
            ctx.closePath();
            ctx.fill();
            const label = "J" + (offset + i + 1);
            ctx.font = `bold ${g.fontSize}px Arial, Helvetica, sans-serif`;
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.lineJoin = "round";
            ctx.lineWidth = g.stroke * 2.2;
            ctx.strokeStyle = "#ffffff";
            ctx.strokeText(label, g.lab.x, g.lab.y);
            ctx.fillStyle = "#000000";
            ctx.fillText(label, g.lab.x, g.lab.y);
        });
        return canvas.toDataURL("image/jpeg", 0.92);
    }
    async save() {
        if (this.state.saving) {
            return;
        }
        this.state.saving = true;
        try {
            const payload = [];
            let offset = 0;
            for (const img of this.state.images) {
                payload.push({
                    id: img.id,
                    markers: img.markers,
                    annotated: img.markers.length ? await this.renderAnnotated(img, offset) : false,
                });
                offset += img.markers.length;
            }
            const res = await this.orm.call("project.task", "vt_save_markers", [[this.taskId], payload]);
            this.state.dirty = false;
            this.notification.add(`Se guardaron ${res.joint_count} juntas. Ya puedes capturar sus datos.`, {
                type: "success",
            });
            this.goBack();
        } finally {
            this.state.saving = false;
        }
    }
    goBack() {
        const bc = this.env.config?.breadcrumbs || [];
        if (bc.length > 1) {
            bc.at(-2).onSelected();
        } else {
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: "project.task",
                res_id: this.taskId,
                views: [[false, "form"]],
            });
        }
    }
    onBack() {
        if (!this.state.dirty) {
            return this.goBack();
        }
        this.dialog.add(ConfirmationDialog, {
            title: "Cambios sin guardar",
            body: "Tienes juntas marcadas sin guardar. ¿Salir sin guardar?",
            confirmLabel: "Salir sin guardar",
            confirm: () => this.goBack(),
            cancel: () => {},
        });
    }
}

registry.category("actions").add("mx_soldic_vt_joint_marker", VtJointMarker);
