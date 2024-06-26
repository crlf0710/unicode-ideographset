import fileinput, re, os, sys, zipfile

preamble = '''// `unicode-ideographset` data tables
//
// Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
// http://www.apache.org/licenses/LICENSE-2.0> or the MIT license
// <LICENSE-MIT or http://opensource.org/licenses/MIT>, at your
// option. This file may not be copied, modified, or distributed
// except according to those terms.

// NOTE: The following code was generated by "scripts/unicode.py", do not edit directly

#![allow(missing_docs, non_upper_case_globals, non_snake_case)]
'''

UNICODE_VERSION = (15, 1, 0)

UNICODE_VERSION_NUMBER = "%s.%s.%s" %UNICODE_VERSION

def fetch(f):
    if not os.path.exists(os.path.basename(f)):
        os.system("curl -O https://www.unicode.org/Public/%s/ucd/%s"
                  % (UNICODE_VERSION_NUMBER, f))

    if not os.path.exists(os.path.basename(f)):
        sys.stderr.write("cannot load %s\n" % f)
        exit(1)

def fetch_unihan(f):
    unihan_zip = "Unihan.zip"
    fetch(unihan_zip)

    if not os.path.exists(os.path.basename(f)):
        with zipfile.ZipFile(unihan_zip) as zip:
            zip.extract(f)

    if not os.path.exists(os.path.basename(f)):
        sys.stderr.write("cannot load %s\n" % f)
        exit(1)

def build_props(f, has_hash = True, prop_filter = None):
    props = {}
    if has_hash:
        re1 = re.compile(r"^ *([0-9A-F]+) *; *([^#]+) *#")
        re2 = re.compile(r"^ *([0-9A-F]+)\.\.([0-9A-F]+) *; *([^#]+) *#")
    else:
        re1 = re.compile(r"^ *([0-9A-F]+) *; *([^#]+)")
        re2 = re.compile(r"^ *([0-9A-F]+)\.\.([0-9A-F]+) *; *([^#]+)")

    for line in fileinput.input(os.path.basename(f), openhook=fileinput.hook_encoded("utf-8")):
        prop = None
        d_lo = 0
        d_hi = 0
        m = re1.match(line)
        if m:
            d_lo = m.group(1)
            d_hi = m.group(1)
            prop = m.group(2).strip()
        else:
            m = re2.match(line)
            if m:
                d_lo = m.group(1)
                d_hi = m.group(2)
                prop = m.group(3).strip()
            else:
                continue
        if prop_filter != None and not prop_filter(prop):
            continue
        d_lo = int(d_lo, 16)
        d_hi = int(d_hi, 16)
        if prop not in props:
            props[prop] = []
        props[prop].append((d_lo, d_hi))
    return props

def build_props_unihan_dict(f, prop_item_expected, prop_item_replacement = None, prop_item_cb = None):
    props = {}
    re1 = re.compile("^U\\+*([0-9A-F]+)[ \\t]*([A-Za-z_0-9]+)[ \\t]*(.*)")
    for line in fileinput.input(os.path.basename(f), openhook=fileinput.hook_encoded("utf-8")):
        m = re1.match(line)
        if not m:
            continue
        line_cp = m.group(1)
        line_prop_item = m.group(2).strip()
        line_prop_value = m.group(3).strip()
        if not line_prop_item == prop_item_expected:
            continue
        line_cp = int(line_cp, 16)
        if prop_item_cb != None:
            prop = prop_item_cb(line_prop_value, line_prop_item)
        else:
            prop = prop_item_replacement
        if prop not in props:
            props[prop] = []
        if len(props[prop]) == 0 or props[prop][-1][1] + 1 != line_cp:
            props[prop].append((line_cp, line_cp))
        else:
            props[prop][-1] = (props[prop][-1][0], line_cp)
    return props

max_codepoint = 0x10FFFF

def flatten_props_to_table(props, gap_prop = ''):
    prop_list = list(props.keys())
    prop_count = len(prop_list)
    subrange_count = [len(props[key]) for key in prop_list]
    subrange_iter = [0 for _ in prop_list]
    prev_prop_id = -1
    cur_codepoint = 0
    table = []
    # print(props)
    while cur_codepoint <= max_codepoint:
        # print("DBG: U+%04X" % cur_codepoint)
        cur_prop_id = -1
        for prop_id in range(prop_count):
            subrange_id = subrange_iter[prop_id]
            if subrange_id >= subrange_count[prop_id]:
                continue
            prop_value = props[prop_list[prop_id]]
            assert(prop_value[subrange_id][0] >= cur_codepoint)
            if prop_value[subrange_id][0] == cur_codepoint:
                cur_prop_id = prop_id
                break
        if cur_prop_id == -1:
            cur_gap_end = max_codepoint
            for prop_id in range(prop_count):
                if subrange_iter[prop_id] >= subrange_count[prop_id]:
                    continue
                assert(props[prop_list[prop_id]][subrange_iter[prop_id]][0] > cur_codepoint)
                prop_gap_end = props[prop_list[prop_id]][subrange_iter[prop_id]][0] - 1
                if prop_gap_end < cur_gap_end:
                    cur_gap_end = prop_gap_end
            table.append(((cur_codepoint, cur_gap_end), gap_prop))
            cur_codepoint = cur_gap_end + 1
            # print("DBG: %s => U+%04X" % ("GAP", cur_codepoint))
            prev_prop_id = -1
            continue
        cur_subrange_id = subrange_iter[cur_prop_id]
        cur_prop = prop_list[cur_prop_id]
        cur_subrange = props[cur_prop][cur_subrange_id]
        if prev_prop_id != cur_prop_id:
            table.append((cur_subrange, cur_prop))
        else:
            table[-1] = ((table[-1][0][0], cur_subrange[1]), cur_prop)
        cur_codepoint = cur_subrange[1] + 1
        # print("DBG: %s => U+%04X" % (cur_prop, cur_codepoint))
        prev_prop_id = cur_prop_id
        subrange_iter[cur_prop_id] += 1
    return table

def merge_tables(table_list, prop_cb):
    table_count = len(table_list)
    subrange_count = [len(table_list[table_id]) for table_id in range(table_count)]
    subrange_iter = [0 for _ in range(table_count)]
    cur_codepoint = 0
    table = []
    # print(props)
    while cur_codepoint <= max_codepoint:
        # print("DBG: U+%04X" % cur_codepoint)
        cur_range_end = max_codepoint + 1
        prop_list = []
        for table_id in range(table_count):
            assert(subrange_iter[table_id] < subrange_count[table_id])
            assert(table_list[table_id][subrange_iter[table_id]][0][0] <= cur_codepoint)
            table_range_end = table_list[table_id][subrange_iter[table_id]][0][1]
            if table_range_end < cur_range_end:
                cur_range_end = table_range_end
            prop_list.append(table_list[table_id][subrange_iter[table_id]][1])
        if cur_range_end > max_codepoint:
            break
        code_range = (cur_codepoint, cur_range_end)
        prop = prop_cb(prop_list, code_range)
        table.append((code_range, prop))
        for table_id in range(table_count):
            if table_list[table_id][subrange_iter[table_id]][0][1] == cur_range_end:
                subrange_iter[table_id] += 1
        cur_codepoint = cur_range_end + 1
    return table

def load_scripts():
    f = "Scripts.txt"
    fetch(f)
    props = build_props(f, True, lambda x: x == "Han" or x == "Tangut" or x == "Nushu" or x == 'Khitan_Small_Script')
    table = flatten_props_to_table(props)
    return table

def load_ui():
    f = "PropList.txt"
    fetch(f)
    def is_ui_prop(prop):
        return prop == 'Unified_Ideograph'
    props = build_props(f, has_hash=False, prop_filter = is_ui_prop)
    table = flatten_props_to_table(props)
    return table

def load_ideographic():
    f = "PropList.txt"
    fetch(f)
    def is_ideographic_prop(prop):
        return prop == 'Ideographic'
    props = build_props(f, has_hash=False, prop_filter = is_ideographic_prop)
    table = flatten_props_to_table(props)
    return table

def load_cjk_radical():
    f = "PropList.txt"
    fetch(f)
    def is_cjk_radical_prop(prop):
        return prop == 'Radical'
    props = build_props(f, has_hash=False, prop_filter = is_cjk_radical_prop)
    table = flatten_props_to_table(props)
    return table

def load_iicore():
    f = "Unihan_IRGSources.txt"
    fetch_unihan(f)
    props = build_props_unihan_dict(f, "kIICore", "IICore")
    table = flatten_props_to_table(props)
    return table

def load_unihancore2020():
    f = "Unihan_DictionaryLikeData.txt"
    fetch_unihan(f)
    props = build_props_unihan_dict(f, "kUnihanCore2020", "UnihanCore2020")
    table = flatten_props_to_table(props)
    return table

def make_ideographset_name(prop_list, code_range):
    [script, ideographic, cjk_radical, ui, iicore, unihancore] = prop_list
    if iicore != '':
        return 'IICoreCJKUnifiedIdeograph'
    elif unihancore != '':
        return 'IICoreAndUnihanCoreCJKUnifiedIdeograph'
    elif ui != '':
        return 'OtherCJKUnifiedIdeograph'
    elif cjk_radical != '':
        if code_range[0] == 0x2E9A and code_range[1] == 0x2E9A: #Reserved
            return 'Other'
        return 'CJKRadicalAndComponent'
    elif ideographic != '':
        if code_range[0] == 0x3006 and code_range[1] == 0x3006: # IDEOGRAPHIC CLOSING MARK
            return 'CJKSpecialIdeograph'
        elif code_range[0] == 0x3007 and code_range[1] == 0x3007: # IDEOGRAPHIC NUMBER ZERO
            return 'CJKSpecialIdeograph'
        elif code_range[0] == 0x3021 and code_range[1] == 0x3029: # Suzhou numeral
            return 'CJKSpecialIdeograph'
        elif code_range[0] == 0x3038 and code_range[1] == 0x303A: # Suzhou numeral
            return 'CJKSpecialIdeograph'
        elif code_range[0] == 0x16FE4 and code_range[1] == 0x16FE4: # Filler
            return 'Other'
        elif code_range[0] == 0x18800:
            assert code_range[1] == 0x18AFF
            return 'TangutRadicalAndComponent'
        elif script == 'Han':
            return 'CJKCompatIdeograph'
        elif script == 'Tangut':
            return 'TangutIdeograph'
        elif script == 'Nushu':
            return 'NushuIdeograph'
        elif script == 'Khitan_Small_Script':
            return 'KhitanSmallScriptIdeograph'
        else:
            print(script + "(%s,%s)" % (escape_codepoint(code_range[0]), escape_codepoint(code_range[1])));
    return "Other"

def load_segments():
    script_table = load_scripts()
    ui_table = load_ui()
    ideographic_table = load_ideographic()
    cjk_radical_table = load_cjk_radical()
    iicore_table, unihancore2020_table = load_iicore(), load_unihancore2020()

    merged_table = merge_tables(
        [script_table, ideographic_table, cjk_radical_table, ui_table, iicore_table, unihancore2020_table],
        make_ideographset_name)
    return merged_table


def emit_util_mod(f):
    f.write("""
pub mod util {
    use core::result::Result::{Ok, Err};

    pub fn bsearch_range_value_table<T: Copy>(c: usize, r: &'static [(usize, usize, T)]) -> Option<T> {
        use core::cmp::Ordering::{Equal, Less, Greater};
        match r.binary_search_by(|&(lo, hi, _)| {
            if lo <= c && c <= hi { Equal }
            else if hi < c { Less }
            else { Greater }
        }) {
            Ok(idx) => {
                let (_, _, cat) = r[idx];
                Some(cat)
            }
            Err(_) => None
        }
    }

}

""")


def format_table_content(f, content, indent):
    line = " "*indent
    first = True
    for chunk in content.split(","):
        if len(line) + len(chunk) < 98:
            if first:
                line += chunk
            else:
                line += ", " + chunk
            first = False
        else:
            f.write(line + ",\n")
            line = " "*indent + chunk
    f.write(line)

def escape_codepoint(c):
    return "0x%04X" % c

def emit_table(f, name, t_data, t_type = "&'static [(usize, usize)]", is_pub=True,
        pfun=lambda x: "(%s,%s)" % (escape_codepoint(x[0]), escape_codepoint(x[1])), is_const=True):
    pub_string = "const"
    if not is_const:
        pub_string = "let"
    if is_pub:
        pub_string = "pub " + pub_string
    f.write("    %s %s: %s = &[\n" % (pub_string, name, t_type))
    data = ""
    first = True
    for dat in t_data:
        if not first:
            data += ","
        first = False
        data += pfun(dat)
    format_table_content(f, data, 8)
    f.write("\n    ];\n\n")

def emit_ideographset_data(f, segments):
    f.write("""
pub mod ideographset_data {
    #[derive(Copy, Clone, Hash, Eq, PartialEq, Ord, PartialOrd, Debug)]
    #[allow(non_camel_case_types)]
    pub enum IdeographSet {
        IICoreCJKUnifiedIdeograph,
        IICoreAndUnihanCoreCJKUnifiedIdeograph,
        OtherCJKUnifiedIdeograph,
        CJKCompatIdeograph,
        CJKSpecialIdeograph,
        TangutIdeograph,
        NushuIdeograph,
        KhitanSmallScriptIdeograph,
        CJKRadicalAndComponent,
        TangutRadicalAndComponent,
        Other,
    }

    #[inline]
    pub fn ideographset_data_lookup(c: char) -> IdeographSet {
        // FIXME: do we want to special case ASCII here?
        match c as usize {
            _ => super::util::bsearch_range_value_table(c as usize, IDEOGRAPHSET_LIST).unwrap()
        }
    }

""")
    emit_table(f, "IDEOGRAPHSET_LIST", segments, "&'static [(usize, usize, IdeographSet)]", is_pub=False,
            pfun=lambda x: "(%s,%s, IdeographSet::%s)" % (escape_codepoint(x[0][0]), escape_codepoint(x[0][1]), x[1].replace('@', '')))
    f.write("}\n\n")

if __name__ == "__main__":
    r = "src/tables.rs"
    if os.path.exists(r):
        os.remove(r)
    with open(r, "w") as rf:
        # write the file's preamble
        rf.write(preamble)

        rf.write("""
/// The version of [Unicode](http://www.unicode.org/)
/// that this version of `unicode-ideographset` is based on.
pub const UNICODE_VERSION: (u64, u64, u64) = (%s, %s, %s);

""" % UNICODE_VERSION)
        segments = load_segments()
        emit_util_mod(rf)
        emit_ideographset_data(rf, segments)
