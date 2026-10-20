"""Write one multi-part, multi-filament object as a 3MF file.

The geometry is plain 3MF core: one mesh object per part and one object
that assembles them as components. The filament of each part goes in
Metadata/model_settings.config, which Bambu Studio (and OrcaSlicer)
reads from any 3MF: <part id> names the mesh object, and the part's
"extruder" metadata is its filament slot, counted from 1. Other object
metadata keys are print settings that override the process preset for
this object.
"""

import zipfile
from xml.sax.saxutils import escape, quoteattr

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>
"""

RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""

APPLICATION = "KiCad bambu3mf"


class Part(object):
    """A named mesh printed with one filament."""

    def __init__(self, name, filament, mesh):
        self.name = name
        self.filament = filament
        self.mesh = mesh


def mm(v):
    """Integer nanometres as an exact decimal millimetre string."""
    q, r = divmod(abs(v), 1000000)
    s = str(q) if not r else "%d.%s" % (q, ("%06d" % r).rstrip("0"))
    return "-" + s if v < 0 else s


def model_xml(title, parts):
    out = ['<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">\n'
        ' <metadata name="Application">%s</metadata>\n'
        ' <metadata name="Title">%s</metadata>\n'
        ' <resources>\n' % (escape(APPLICATION), escape(title))]
    for pid, part in enumerate(parts, 1):
        out.append('  <object id="%d" type="model" name=%s>\n'
            '   <mesh>\n    <vertices>\n' % (pid, quoteattr(part.name)))
        out.extend('     <vertex x="%s" y="%s" z="%s"/>\n' %
            (mm(x), mm(y), mm(z)) for x, y, z in part.mesh.vertices)
        out.append('    </vertices>\n    <triangles>\n')
        out.extend('     <triangle v1="%d" v2="%d" v3="%d"/>\n' % t
            for t in part.mesh.triangles)
        out.append('    </triangles>\n   </mesh>\n  </object>\n')
    oid = len(parts) + 1
    out.append('  <object id="%d" type="model" name=%s>\n   <components>\n' %
        (oid, quoteattr(title)))
    out.extend('    <component objectid="%d"/>\n' % pid
        for pid in range(1, oid))
    out.append('   </components>\n  </object>\n </resources>\n'
        ' <build>\n  <item objectid="%d"/>\n </build>\n</model>\n' % oid)
    return "".join(out)


def settings_xml(title, parts, settings):
    oid = len(parts) + 1
    out = ['<?xml version="1.0" encoding="UTF-8"?>\n<config>\n'
        '  <object id="%d">\n'
        '    <metadata key="name" value=%s/>\n'
        '    <metadata key="extruder" value="%d"/>\n' %
        (oid, quoteattr(title), parts[0].filament)]
    out.extend('    <metadata key=%s value=%s/>\n' %
        (quoteattr(k), quoteattr(v)) for k, v in settings)
    for pid, part in enumerate(parts, 1):
        out.append('    <part id="%d" subtype="normal_part">\n'
            '      <metadata key="name" value=%s/>\n'
            '      <metadata key="extruder" value="%d"/>\n'
            '    </part>\n' % (pid, quoteattr(part.name), part.filament))
    out.append('  </object>\n</config>\n')
    return "".join(out)


def write(path, title, parts, settings=()):
    """Write parts as one object called title to the 3MF file at path.
    settings are (key, value) print settings for the object, as Bambu
    Studio names them; they show as the object's own settings there."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("3D/3dmodel.model", model_xml(title, parts))
        z.writestr("Metadata/model_settings.config",
            settings_xml(title, parts, settings))
