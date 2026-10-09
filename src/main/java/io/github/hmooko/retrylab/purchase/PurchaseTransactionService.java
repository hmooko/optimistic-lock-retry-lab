package io.github.hmooko.retrylab.purchase;

import io.github.hmooko.retrylab.domain.Product;
import io.github.hmooko.retrylab.domain.ProductRepository;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@Service
public class PurchaseTransactionService {
    private final ProductRepository productRepository;

    public PurchaseTransactionService(ProductRepository productRepository) {
        this.productRepository = productRepository;
    }

    @Transactional(isolation = Isolation.READ_COMMITTED)
    public void purchaseOptimistic(long productId) {
        purchaseOptimisticInternal(productId, 0L);
    }

    @Transactional(isolation = Isolation.READ_COMMITTED)
    public void purchaseOptimistic(long productId, long txWorkMs) {
        purchaseOptimisticInternal(productId, txWorkMs);
    }

    @Transactional(isolation = Isolation.READ_COMMITTED)
    public void purchasePessimistic(long productId) {
        purchasePessimisticInternal(productId, 0L);
    }

    @Transactional(isolation = Isolation.READ_COMMITTED)
    public void purchasePessimistic(long productId, long txWorkMs) {
        purchasePessimisticInternal(productId, txWorkMs);
    }

    private void purchaseOptimisticInternal(long productId, long txWorkMs) {
        Product product = productRepository.findById(productId)
                .orElseThrow(() -> notFound(productId));
        product.decreaseStock();
        simulateBusinessWork(txWorkMs);
    }

    private void purchasePessimisticInternal(long productId, long txWorkMs) {
        Product product = productRepository.findByIdForUpdate(productId)
                .orElseThrow(() -> notFound(productId));
        product.decreaseStock();
        simulateBusinessWork(txWorkMs);
    }

    private void simulateBusinessWork(long txWorkMs) {
        if (txWorkMs <= 0) return;
        try {
            Thread.sleep(txWorkMs);
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("synthetic transaction work interrupted", interrupted);
        }
    }

    private ResponseStatusException notFound(long productId) {
        return new ResponseStatusException(HttpStatus.NOT_FOUND, "product not found: " + productId);
    }
}
