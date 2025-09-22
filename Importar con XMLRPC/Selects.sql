-- Select categorias (Inventario/tpv)
SELECT *
FROM (
    SELECT
        r.descr AS name,
        CASE 
            WHEN r.idsrubro <> r.id_rubro THEN rp.descr
            ELSE ''
        END AS [parent_id/id],
        'Manual' AS property_valuation,
        'Precio estándar' AS property_cost_method
    FROM Rubros r
    LEFT JOIN Rubros rp ON r.idsrubro = rp.id_rubro

    UNION ALL

    SELECT
        'SIN CATEGORIA' AS name,
        '' AS [parent_id/id],
        'Manual' AS property_valuation,
        'Precio estándar' AS property_cost_method
) AS rubros_completos
ORDER BY name;








-- Select Marcas.
SELECT
    m.descmarca AS name
FROM Marcas m;






-- Select Proveedores:
SELECT
    ISNULL(p.razon_social, '') AS name,
    'company' AS company_type,
    'CUIT' AS [l10n_latam_identification_type_id/name],
    'IVA Responsable Inscripto' AS l10n_ar_afip_responsibility_type_id,

    CASE 
        WHEN p.cuit IS NULL OR p.cuit = '' THEN '' 
        ELSE LEFT(REPLACE(REPLACE(REPLACE(p.cuit, '-', ''), '.', ''), ' ', ''), 11) 
    END AS vat,

    ISNULL(p.dir, '') AS street,
    ISNULL(p.telefono, '') AS phone_mobile_search,

    -- Valores estáticos para Odoo (inversos)
    0 AS customer_rank,
    1 AS supplier_rank

FROM proveedores p;






-- Select clientes:
SELECT
    -- Nombre completo uniendo apel + nom
    ISNULL(LTRIM(RTRIM(c.apel)), '') + 
    CASE WHEN c.apel IS NOT NULL AND c.apel <> '' AND c.nom IS NOT NULL AND c.nom <> '' 
         THEN ' ' ELSE '' END + 
    ISNULL(LTRIM(RTRIM(c.nom)), '') AS name,

    -- Campo estático
    'company' AS company_type,

    -- l10n_latam_identification_type_id/name (CUIT o DNI)
    CASE 
        WHEN c.sit_impositiva = 'Inscripto' THEN 'CUIT'
        WHEN c.sit_impositiva = 'Exento' THEN 'CUIT'
        WHEN c.sit_impositiva = 'Consumidor final' THEN 'DNI'
        ELSE 'DNI'
    END AS [l10n_latam_identification_type_id/name],

    -- l10n_ar_afip_responsibility_type_id (IVA Responsable, Exento, etc.)
    CASE 
        WHEN c.sit_impositiva = 'Exento' THEN 'IVA Sujeto Exento'
        WHEN c.sit_impositiva = 'Inscripto' THEN 'IVA Responsable Inscripto'
        WHEN c.sit_impositiva = 'Consumidor final' THEN 'Consumidor Final'
        ELSE 'Consumidor Final'
    END AS l10n_ar_afip_responsibility_type_id,

    -- vat (CUIT o DNI limpio)
    CASE 
        WHEN (c.sit_impositiva = 'Consumidor final' OR c.sit_impositiva IS NULL)
             THEN 
                CASE 
                    WHEN c.dni IS NOT NULL 
                         AND LEN(REPLACE(REPLACE(c.dni, '-', ''), '.', '')) = 8
                         AND ISNUMERIC(REPLACE(REPLACE(c.dni, '-', ''), '.', '')) = 1
                    THEN REPLACE(REPLACE(c.dni, '-', ''), '.', '')
                    ELSE '99999999'
                END
        ELSE 
            CASE 
                WHEN c.cuit IS NOT NULL 
                THEN LEFT(REPLACE(REPLACE(REPLACE(c.cuit, '-', ''), '.', ''), ' ', ''), 11)
                ELSE ''
            END
    END AS vat,

    -- Dirección
    ISNULL(c.dir, '') AS street,

    -- Teléfono
    ISNULL(c.telefono, '') AS phone_mobile_search,

    -- Valores estáticos para Odoo (inversos)
    1 AS customer_rank, 
    0 AS supplier_rank

FROM clientes c;













-- Select Articulos:
-- Declaración para definir qué campo usar como default_code
DECLARE @usarCodigoInterno BIT
SET @usarCodigoInterno = 1

SELECT
    -- Nombre del producto
    ISNULL(a.descripcion, '') AS name,

    -- Descripción en formato HTML
    '<p>' + ISNULL(LTRIM(RTRIM(a.descripcion)), '') + '</p>' AS description,

    -- Código de barras: solo si existe y es el último repetido
    CASE 
        WHEN a.cod_barra IS NULL OR LTRIM(RTRIM(a.cod_barra)) = '' THEN ''
        WHEN a.id_art = (
            SELECT MAX(a2.id_art)
            FROM articulos a2
            WHERE a2.cod_barra = a.cod_barra
        ) THEN a.cod_barra
        ELSE ''
    END AS barcode,

    -- Impuestos según ID
    CASE 
        WHEN a.idimpuesto = 1 THEN 'IVA 21%'
        WHEN a.idimpuesto = 2 THEN 'IVA 10,5%'
        WHEN a.idimpuesto = 3 THEN 'IVA 27%'
        ELSE ''
    END AS [taxes_id/id],

    -- Código interno o de fabricante según variable
    CASE 
        WHEN @usarCodigoInterno = 1 THEN ISNULL(a.codigo_interno, '')
        ELSE ISNULL(a.codfabricante, '')
    END AS default_code,

    -- Costos y precios
    ISNULL(a.prec_costo, 0) AS standard_price,
    ISNULL(a.prec_vta, 0) AS list_price,

    -- Valores estáticos
    'company' AS purchase_ok,
    'company' AS sale_ok,
    'company' AS available_in_pos,

    -- Marca
    ISNULL(m.descmarca, '') AS product_brand_id,

    -- Proveedor
    ISNULL(p.razon_social, '') AS seller_ids,

    -- Rubro para categ_id y pos_categ_id
    ISNULL(r.descr, 'SIN CATEGORIA') AS categ_id,
    ISNULL(r.descr, 'SIN CATEGORIA') AS pos_categ_id,

    -- Valores estáticos adicionales
    'company' AS detailed_type,
    'company' AS purchase_method

FROM articulos a
LEFT JOIN marcas m ON a.idmarca = m.idmarca
LEFT JOIN proveedores p ON a.id_prov = p.id_prov
LEFT JOIN rubros r ON a.id_rubro = r.id_rubro
WHERE a.inhabilitado = 0
  AND a.descripcion IS NOT NULL
  AND LTRIM(RTRIM(a.descripcion)) <> ''




