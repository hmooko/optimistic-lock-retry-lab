package io.github.hmooko.retrylab.purchase;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/purchases")
public class PurchaseController {
    private final PurchaseService purchaseService;

    public PurchaseController(PurchaseService purchaseService) {
        this.purchaseService = purchaseService;
    }

    @PostMapping("/{productId}")
    public ResponseEntity<PurchaseResponse> purchase(
            @PathVariable long productId,
            @RequestParam PurchaseStrategy strategy,
            @RequestParam(defaultValue = "0") long txWorkMs,
            @RequestParam(required = false) Integer maxRetries
    ) {
        return ResponseEntity.ok(
                purchaseService.purchase(productId, strategy, txWorkMs, maxRetries));
    }
}
