package br.com.seuprojeto.ceps_api.controller;

import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
public class CepController {

    // ==================== ENDPOINT 1: TODOS OS CEPs ====================
    @GetMapping("/ceps")
    public ResponseEntity<?> getCeps() {
        String host = "pub400.com";
        String user = "AROSASSE";
        String password = System.getenv("AS400_PASSWORD");
        String library = "AROSASSE1";
        String url = "jdbc:as400://" + host + ";libraries=" + library + ";naming=sql";

        List<Map<String, String>> ceps = new ArrayList<>();

        try {
            Class.forName("com.ibm.as400.access.AS400JDBCDriver");

            try (Connection conn = DriverManager.getConnection(url, user, password);
                 PreparedStatement stmt = conn.prepareStatement(
                         "SELECT ID_CEPS, UF, CIDADE, CEP_DE, CEP_ATE FROM " + library + ".CEPS");
                 ResultSet rs = stmt.executeQuery()) {

                while (rs.next()) {
                    Map<String, String> item = new HashMap<>();
                    item.put("id", rs.getString("ID_CEPS"));
                    item.put("uf", rs.getString("UF"));
                    item.put("cidade", rs.getString("CIDADE"));
                    item.put("cepDe", rs.getString("CEP_DE"));
                    item.put("cepAte", rs.getString("CEP_ATE"));
                    ceps.add(item);
                }
            }
            return ResponseEntity.ok(ceps);

        } catch (ClassNotFoundException e) {
            return ResponseEntity.status(500).body("Driver JDBC não encontrado: " + e.getMessage());
        } catch (SQLException e) {
            return ResponseEntity.status(500).body("Erro de SQL: " + e.getMessage());
        } catch (Exception e) {
            return ResponseEntity.status(500).body("Erro inesperado: " + e.getMessage());
        }
    }

    // ==================== ENDPOINT 2: PAGINAÇÃO E BUSCA ====================
    @GetMapping("/ceps/page")
    public ResponseEntity<Map<String, Object>> getCepsPaginated(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "10") int size,
            @RequestParam(required = false) String cidade) {

        String host = "pub400.com";
        String user = "AROSASSE";
        String password = System.getenv("AS400_PASSWORD");
        String library = "AROSASSE1";
        String url = "jdbc:as400://" + host + ";libraries=" + library + ";naming=sql";

        Map<String, Object> response = new HashMap<>();

        try {
            Class.forName("com.ibm.as400.access.AS400JDBCDriver");

            try (Connection conn = DriverManager.getConnection(url, user, password)) {

                // ----- Montar WHERE dinâmico (com segurança) -----
                StringBuilder whereClause = new StringBuilder();
                List<String> paramValues = new ArrayList<>();

                if (cidade != null && !cidade.trim().isEmpty()) {
                    whereClause.append(" WHERE UPPER(CIDADE) LIKE ?");
                    paramValues.add("%" + cidade.trim().toUpperCase() + "%");
                }

                // ----- Contar total de registros (com filtro) -----
                String countSql = "SELECT COUNT(*) FROM " + library + ".CEPS" + whereClause;
                long total;
                try (PreparedStatement stmtCount = conn.prepareStatement(countSql)) {
                    for (int i = 0; i < paramValues.size(); i++) {
                        stmtCount.setString(i + 1, paramValues.get(i));
                    }
                    try (ResultSet rsCount = stmtCount.executeQuery()) {
                        rsCount.next();
                        total = rsCount.getLong(1);
                    }
                }

                // ----- Buscar registros paginados -----
                String sql = "SELECT ID_CEPS, UF, CIDADE, CEP_DE, CEP_ATE FROM " + library + ".CEPS"
                        + whereClause
                        + " OFFSET ? ROWS FETCH NEXT ? ROWS ONLY";

                List<Map<String, String>> ceps = new ArrayList<>();
                try (PreparedStatement stmt = conn.prepareStatement(sql)) {
                    int index = 1;
                    for (String val : paramValues) {
                        stmt.setString(index++, val);
                    }
                    stmt.setInt(index++, page * size);
                    stmt.setInt(index, size);

                    try (ResultSet rs = stmt.executeQuery()) {
                        while (rs.next()) {
                            Map<String, String> item = new HashMap<>();
                            item.put("id", rs.getString("ID_CEPS"));
                            item.put("uf", rs.getString("UF"));
                            item.put("cidade", rs.getString("CIDADE"));
                            item.put("cepDe", rs.getString("CEP_DE"));
                            item.put("cepAte", rs.getString("CEP_ATE"));
                            ceps.add(item);
                        }
                    }
                }

                // ----- Montar resposta JSON -----
                response.put("content", ceps);
                response.put("totalElements", total);
                response.put("page", page);
                response.put("size", size);
                response.put("totalPages", (int) Math.ceil((double) total / size));

                return ResponseEntity.ok(response);
            }

        } catch (ClassNotFoundException e) {
            response.put("error", "Driver JDBC não encontrado: " + e.getMessage());
            return ResponseEntity.status(500).body(response);
        } catch (SQLException e) {
            response.put("error", "Erro de SQL: " + e.getMessage());
            return ResponseEntity.status(500).body(response);
        } catch (Exception e) {
            response.put("error", "Erro inesperado: " + e.getMessage());
            return ResponseEntity.status(500).body(response);
        }
    }

    // ==================== ENDPOINT 3: EXPORTAR CSV (CORRIGIDO) ====================
    @GetMapping(value = "/ceps/export", produces = "text/csv;charset=UTF-8")
    public ResponseEntity<byte[]> exportCsv(@RequestParam(required = false) String cidade) throws SQLException {
        String host = "pub400.com";
        String user = "AROSASSE";
        String password = System.getenv("AS400_PASSWORD");
        String library = "AROSASSE1";
        String url = "jdbc:as400://" + host + ";libraries=" + library + ";naming=sql";

        try {
            Class.forName("com.ibm.as400.access.AS400JDBCDriver");

            // Montar WHERE dinâmico
            String whereClause = "";
            String cidadeParam = null;
            if (cidade != null && !cidade.trim().isEmpty()) {
                whereClause = " WHERE UPPER(CIDADE) LIKE ?";
                cidadeParam = "%" + cidade.trim().toUpperCase() + "%";
            }

            // Consulta sem paginação (todos os registros)
            String sql = "SELECT ID_CEPS, UF, CIDADE, CEP_DE, CEP_ATE FROM " + library + ".CEPS" + whereClause;

            // Construir CSV em memória
            StringBuilder csv = new StringBuilder();
            csv.append("ID,UF,Cidade,CEP_DE,CEP_ATE\n");

            try (Connection conn = DriverManager.getConnection(url, user, password);
                 PreparedStatement stmt = conn.prepareStatement(sql)) {

                if (cidadeParam != null) {
                    stmt.setString(1, cidadeParam);
                }

                try (ResultSet rs = stmt.executeQuery()) {
                    while (rs.next()) {
                        csv.append(rs.getString("ID_CEPS")).append(",")
                           .append(rs.getString("UF")).append(",")
                           .append(rs.getString("CIDADE")).append(",")
                           .append(rs.getString("CEP_DE")).append(",")
                           .append(rs.getString("CEP_ATE")).append("\n");
                    }
                }
            }

            // 🔥 LINHA CORRIGIDA (usando StandardCharsets.UTF_8)
            byte[] bytes = csv.toString().getBytes(StandardCharsets.UTF_8);

            // Configurar cabeçalhos para download
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.parseMediaType("text/csv;charset=UTF-8"));
            headers.setContentDisposition(
                    org.springframework.http.ContentDisposition.builder("attachment")
                            .filename("ceps_" + (cidade != null ? cidade : "todos") + ".csv")
                            .build()
            );

            return new ResponseEntity<>(bytes, headers, HttpStatus.OK);

        } catch (ClassNotFoundException e) {
            throw new SQLException("Driver não encontrado", e);
        }
    }
}