/** @odoo-module */

import { PosDB } from "@point_of_sale/app/store/db";
import { patch } from "@web/core/utils/patch";

console.info("Bravo POS alias barcode patch loaded v19.0.2.2.5");

function collectionValues(products) {
    if (!products) return [];
    if (Array.isArray(products)) return products;
    if (typeof products === "object") return Object.values(products);
    return [];
}

function parseBravoAliases(product) {
    if (!product) return [];
    let aliases = [];
    if (product.bravo_barcodes_json) {
        try {
            const parsed = JSON.parse(product.bravo_barcodes_json);
            if (Array.isArray(parsed)) aliases = aliases.concat(parsed);
        } catch (_) {}
    }
    if (product.bravo_all_barcodes) {
        aliases = aliases.concat(String(product.bravo_all_barcodes).split(/[\s,;|]+/));
    }
    if (product.barcode) {
        aliases = aliases.filter((barcode) => String(barcode || "").trim() !== String(product.barcode || "").trim());
    }
    return [...new Set(aliases.map((barcode) => String(barcode || "").trim()).filter(Boolean))];
}

function indexBravoAliases(db, products) {
    if (!db || !db.product_by_barcode) return;
    for (const product of collectionValues(products)) {
        for (const barcode of parseBravoAliases(product)) {
            if (!db.product_by_barcode[barcode]) {
                db.product_by_barcode[barcode] = product;
            }
        }
    }
}

patch(PosDB.prototype, {
    _product_search_string(product) {
        let str = super._product_search_string(...arguments);
        const aliases = parseBravoAliases(product);
        if (aliases.length) {
            if (str.endsWith("\n")) {
                str = str.slice(0, -1) + "|" + aliases.join("|") + "\n";
            } else {
                str += "|" + aliases.join("|");
            }
        }
        return str;
    },

    add_products(products) {
        const res = super.add_products(...arguments);
        indexBravoAliases(this, products);
        return res;
    },

    get_product_by_barcode(barcode) {
        const product = super.get_product_by_barcode ? super.get_product_by_barcode(...arguments) : this.product_by_barcode?.[barcode];
        if (product) return product;
        return this.product_by_barcode?.[String(barcode || "").trim()];
    },
});
