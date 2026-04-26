window.addEventListener('load', function() {
    // Comprueba que exista el widget de OSM
    if (window.OSMWidget && OSMWidget.map) {
        var map = OSMWidget.map;

        // Desactiva todas las interacciones
        map.dragging.disable();
        map.touchZoom.disable();
        map.doubleClickZoom.disable();
        map.scrollWheelZoom.disable();
        map.boxZoom.disable();
        map.keyboard.disable();

        // Opcional: quitar controles de zoom
        if (map.zoomControl) map.zoomControl.remove();
    }
});
