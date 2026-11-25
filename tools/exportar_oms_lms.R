# Extrai tabelas de referência embarcadas nos pacotes WHO anthro e anthroplus.
# Uso temporário de auditoria; não altera o produto.
dir.create("tmp/oms-lms", recursive = TRUE, showWarnings = FALSE)
envs <- list()
for (pkg in c("anthro", "anthroplus")) {
  b64 <- paste(readLines(file.path("tmp", paste0(pkg, "_sysdata.rda.b64")), warn = FALSE), collapse = "")
  raw <- base64enc::base64decode(b64)
  rda <- tempfile(fileext = ".rda")
  writeBin(raw, rda)
  env <- new.env(parent = emptyenv())
  load(rda, envir = env)
  envs[[pkg]] <- env
  cat("PACKAGE", pkg, "\\n")
  for (nm in ls(env, all.names = TRUE)) {
    obj <- get(nm, envir = env)
    if (is.data.frame(obj)) {
      cat("DATAFRAME", nm, nrow(obj), ncol(obj), paste(names(obj), collapse = ","), "\\n")
      write.csv(obj, file.path("tmp/oms-lms", paste0(pkg, "_", nm, ".csv")),
                row.names = FALSE, na = "")
    }
  }
}
make_rows <- function(df, indicador, referencia, unidade, limite, medida_col = NULL) {
  df <- df[df$age >= 0 & df$age <= limite, , drop = FALSE]
  data.frame(
    indicador = indicador,
    referencia = referencia,
    sexo = ifelse(df$sex == 1, "H", "M"),
    idade_dias = if (unidade == "dias") df$age else NA_real_,
    idade_meses = if (unidade == "meses") df$age else NA_real_,
    L = df$l, M = df$m, S = df$s,
    medida = if (is.null(medida_col)) "" else as.character(df[[medida_col]]),
    stringsAsFactors = FALSE
  )
}
a <- envs$anthro
p <- envs$anthroplus
linhas <- list(
  make_rows(a$growthstandards_bmianthro, "imc_idade", "oms_2006", "dias", 1856),
  make_rows(a$growthstandards_weianthro, "peso_idade", "oms_2006", "dias", 1856),
  make_rows(a$growthstandards_lenanthro, "estatura_idade", "oms_2006", "dias", 1856, "loh"),
  make_rows(p$bfa_growth_standards, "imc_idade", "oms_2007", "meses", 228),
  make_rows(p$wfa_growth_standards, "peso_idade", "oms_2007", "meses", 120),
  make_rows(p$hfa_growth_standards, "estatura_idade", "oms_2007", "meses", 228)
)
tabela <- do.call(rbind, linhas)
write.csv(tabela, "tmp/oms-lms/oms_lms.csv", row.names = FALSE, na = "")
cat("COMBINED", nrow(tabela), "rows\\n")
