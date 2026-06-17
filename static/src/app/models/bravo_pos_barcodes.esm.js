/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { normalize } from "@web/core/l10n/utils";
import { ProductProduct } from "@point_of_sale/app/models/product_product";
import { RAW_SYMBOL } from "@point_of_sale/app/models/related_models/utils";

console.info("Bravo POS alias barcode patch loaded for Odoo 19 related models v19.0.1.1.0");

function clean(code) {
    return String(code || "").trim();
}

function unique(codes) {
    return [...new Set(codes.map(clean).filter(Boolean))];
}

function parseJsonList(value) {
    try {
        const parsed = JSON.parse(value || "[]");
        return Array.isArray(parsed) ? parsed : [];
    } catch (_) {
        return [];
    }
}

function splitCodes(value) {
    return String(value || "")
        .split(/[\s,;|]+/)
        .map(clean)
        .filter(Boolean);
}

function aliasCodesFromRaw(raw) {
    const primary = clean(raw?.barcode);
    return unique([
        ...parseJsonList(raw?.bravo_barcodes_json),
        ...splitCodes(raw?.bravo_all_barcodes),
    ]).filter((code) => code !== primary);
}

function ensureBravoBarcodeLookup(productModel) {
    if (!productModel || productModel.__bravoAliasGetByPatched) {
        return;
    }

    productModel.__bravoAliasGetByPatched = true;
    productModel.__bravoProductByBarcode = productModel.__bravoProductByBarcode || new Map();
    const originalGetBy = productModel.getBy.bind(productModel);

    productModel.getBy = function (fieldName, value) {
        const result = originalGetBy(fieldName, value);
        if (result) {
            // product.product.barcode is unique in normal POS data, so this should
            // normally be a ProductProduct. If another patch makes the index
            // multivalued and returns an array, keep POS callers from receiving
            // an array where they expect one product.
            return Array.isArray(result) ? result[0] : result;
        }
        if (fieldName === "barcode") {
            return this.__bravoProductByBarcode?.get(clean(value));
        }
        return result;
    };
}

function reindexBravoAliases(product) {
    const model = product.model;
    ensureBravoBarcodeLookup(model);

    const map = model.__bravoProductByBarcode;
    for (const oldCode of product.__bravoAliasCodes || []) {
        if (map.get(oldCode) === product) {
            map.delete(oldCode);
        }
    }

    const aliases = aliasCodesFromRaw(product[RAW_SYMBOL]);
    product.__bravoAliasCodes = aliases;

    for (const code of aliases) {
        if (!map.has(code)) {
            map.set(code, product);
        }
    }
}

patch(ProductProduct.prototype, {
    setup(vals) {
        super.setup(...arguments);
        reindexBravoAliases(this);
        this._searchString = null;
        this.product_tmpl_id?.onUpdate?.();
    },

    get searchString() {
        if (this._searchString) {
            return this._searchString;
        }
        const raw = this[RAW_SYMBOL] || {};
        const aliases = aliasCodesFromRaw(raw);
        const text = [this.display_name, this.barcode, this.default_code, ...aliases]
            .filter(Boolean)
            .join(" ");
        this._searchString = normalize(text);
        return this._searchString;
    },
});
