# Extrai tabelas de referência embarcadas nos pacotes WHO anthro e anthroplus.
# Uso temporário de auditoria; não altera o produto.
dir.create("tmp/oms-lms", recursive = TRUE, showWarnings = FALSE)
for (pkg in c("anthro", "anthroplus")) {
  b64 <- paste(readLines(file.path("tmp", paste0(pkg, "_sysdata.rda.b64")), warn = FALSE), collapse = "")
  raw <- base64enc::base64decode(b64)
  rda <- tempfile(fileext = ".rda")
  writeBin(raw, rda)
  env <- new.env(parent = emptyenv())
  load(rda, envir = env)
  cat("PACKAGE", pkg, "\n")
  for (nm in ls(env, all.names = TRUE)) {
    obj <- get(nm, envir = env)
    if (is.data.frame(obj)) {
      cat("DATAFRAME", nm, nrow(obj), ncol(obj), paste(names(obj), collapse = ","), "\n")
      write.csv(obj, file.path("tmp/oms-lms", paste0(pkg, "_", nm, ".csv")),
                row.names = FALSE, na = "")
    } else if (is.matrix(obj)) {
      cat("MATRIX", nm, nrow(obj), ncol(obj), paste(colnames(obj), collapse = ","), "\n")
      write.csv(as.data.frame(obj), file.path("tmp/oms-lms", paste0(pkg, "_", nm, ".csv")),
                row.names = FALSE, na = "")
    } else {
      cat("OTHER", nm, paste(class(obj), collapse = "/"), "\n")
    }
  }
}
