<!--
  TerraScope sample QGIS style for a categorical classification raster.

  Default 6-class palette: water, urban, bare, low veg, high veg, snow.
  Users can edit Symbology in the layer properties; this is just a sensible
  starting point so freshly added results aren't grey.
-->
<qgis version="3.40" hasScaleBasedVisibilityFlag="0" maxScale="0" minScale="0" styleCategories="AllStyleCategories">
  <renderer-v2 type="paletted" forceraster="0">
    <colorPalette>
      <paletteEntry value="1" color="#1f77b4" label="Water"/>
      <paletteEntry value="2" color="#7f7f7f" label="Urban"/>
      <paletteEntry value="3" color="#bcbd22" label="Bare ground"/>
      <paletteEntry value="4" color="#8c564b" label="Low vegetation"/>
      <paletteEntry value="5" color="#2ca02c" label="High vegetation"/>
      <paletteEntry value="6" color="#ffffff" label="Snow / ice"/>
    </colorPalette>
  </renderer-v2>
  <pipe>
    <rasterresampler maxOversampling="2"/>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
