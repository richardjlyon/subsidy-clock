import catalogue from '../site/data/catalogue.json' assert { type: 'json' };

const itemsById = {};
let idSeq = 0;
catalogue.forEach(cat => {
  cat.items.forEach(it => {
    const id = idSeq++;
    itemsById[id] = {
      name: it.n,
      cost: it.c,
      color: cat.color
    };
  });
});

export function decodeCode(code) {
  try {
    const cleanB64 = code.replace(/-/g, '+').replace(/_/g, '/');
    const bin = atob(cleanB64);
    const a = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) {
      a[i] = bin.charCodeAt(i);
    }
    
    let i = 0;
    const cur = () => a[i++];
    const readV = () => {
      let r = 0, s = 0, x;
      do {
        x = a[i++];
        r |= (x & 127) << s;
        s += 7;
      } while (x & 128);
      return r >>> 0;
    };
    
    const version = cur();
    const perspIndex = cur();
    const scaleIndex = cur();
    const n = readV();
    
    const spentItems = [];
    let totalCost = 0;
    
    for (let e = 0; e < n; e++) {
      const id = readV();
      const count = readV();
      const item = itemsById[id];
      if (item) {
        spentItems.push({
          id,
          name: item.name,
          count,
          costPerUnit: item.cost,
          totalCost: item.cost * count,
          color: item.color
        });
        totalCost += item.cost * count;
      }
    }
    
    return {
      version,
      perspIndex,
      scaleIndex,
      spentItems,
      totalCost
    };
  } catch (e) {
    console.error("Error decoding code", e);
    return null;
  }
}

export function formatGBP(n) {
  return '£' + Math.round(n).toLocaleString('en-GB');
}

export function formatShort(n) {
  const a = Math.abs(n);
  if (a >= 1e9) return '£' + (n / 1e9).toFixed(n / 1e9 >= 100 ? 0 : 1).replace(/\.0$/, '') + 'bn';
  if (a >= 1e6) return '£' + (n / 1e6).toFixed(n / 1e6 >= 100 ? 0 : 1).replace(/\.0$/, '') + 'm';
  if (a >= 1e3) return '£' + Math.round(n / 1e3) + 'k';
  return '£' + Math.round(n);
}
